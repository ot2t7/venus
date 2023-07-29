# first, import all necessary modules
from pathlib import Path
from time import sleep

import cv2 as cv
import depthai
import numpy as np
from matplotlib import pyplot as plt
import torch

pipeline = depthai.Pipeline()
pipeline.setOpenVINOVersion(depthai.OpenVINO.VERSION_2021_4)

# Camera Size
width = 300
height = 300

cam_rgb = pipeline.create(depthai.node.ColorCamera)
cam_rgb.setPreviewSize(width, height)
cam_rgb.setInterleaved(False)

xout_rgb = pipeline.create(depthai.node.XLinkOut)
xout_rgb.setStreamName("rgb")
cam_rgb.preview.link(xout_rgb.input)

# Query Image
img1 = cv.imread("Bottle.png", cv.IMREAD_GRAYSCALE)
min_match_count = 10

# Initiate SIFT detector
sift = cv.SIFT_create()
kp1, des1 = sift.detectAndCompute(img1,None)

def show_results(image, pad_loc):
    if pad_loc is not None:
        center_point = (int(width / 2), int(height / 2))
        cv.circle(image, pad_loc, 10, (0, 0, 255), 6)
        cv.putText(image, str(pad_loc), (50, 50), cv.FONT_HERSHEY_TRIPLEX, 1.0, (0, 0, 255), 2)
        cv.line(image, center_point, pad_loc, (0, 0, 255), 5)
        cv.imshow("Point=Pad Location", image)
    else:
        cv.imshow("Point=Pad Location", image)

def get_most_recent_img(q_rgb):
    all_in = q_rgb.tryGetAll()
    # Is the queue full? Let's clear the entire queue
    while len(all_in) == q_rgb.getMaxSize():
        all_in = q_rgb.tryGetAll()
    # Is the queue empty now?
    if len(all_in) == 0:
        return None

    # Get the last photo in the queue, the latest one
    return all_in[len(all_in) - 1].getCvFrame()

def pattern_detection_tick(sift, kp1, des1, image):
    # Convert to grayscale
    img2 = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

    # Find the keypoints and descriptors with SIFT
    kp2, des2 = sift.detectAndCompute(img2, None)
    if des2 is None:
        print("There are no camera descriptors!")
        return
    if len(des2) == 1:
        print("There are not enough camera descriptors!")
        return

    # Match the descriptors of the input image, and the pad
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
    search_params = dict(checks=50)   # or pass empty dictionary
    flann = cv.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1,des2,k=2)

    # store all the good matches as per Lowe's ratio test.
    good = []
    for m, n in matches:
        if m.distance < 0.7*n.distance:
            good.append(m)

    pad_loc = None
    if len(good)>min_match_count:
        dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
        pad_loc = np.average(dst_pts, axis=(0, 1))
        pad_loc = (int(pad_loc[0]), int(pad_loc[1]))
        print("gagag!")
        return pad_loc
    else:
        print("Not enough matches are found - {}/{}".format(len(good), min_match_count) )

def homography_tick(sift, kp1, des1, image):
    # Convert to grayscale
    img2 = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

    # Find the keypoints and descriptors with SIFT
    kp2, des2 = sift.detectAndCompute(img2, None)
    if des2 is None:
        print("There are no camera descriptors!")
        return
    if len(des2) == 1:
        print("There are not enough camera descriptors!")
        return

    # Match the descriptors of the input image, and the pad
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
    search_params = dict(checks = 50)
    flann = cv.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1,des2,k=2)

    # store all the good matches as per Lowe's ratio test.
    good = []
    for m,n in matches:
        if m.distance < 0.7*n.distance:
            good.append(m)

    pad_loc = None
    if len(good)>min_match_count:
        src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
        dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
        M, mask = cv.findHomography(src_pts, dst_pts, cv.RANSAC,5.0)
        if M is not None:
            h,w = img1.shape
            pts = np.float32([ [0,0],[0,h-1],[w-1,h-1],[w-1,0] ]).reshape(-1,1,2)
            dst = cv.perspectiveTransform(pts,M)
            dst = np.int32(dst)
            #print("We got some homography!! " + str(dst))
            image = cv.polylines(image,[dst],True,(255, 0, 0),3, cv.LINE_AA)
            print("We got a mask!!! " + str(mask.ravel().tolist()))
    else:
        print("Not enough matches are found - {}/{}".format(len(good), min_match_count) )

with depthai.Device(pipeline, usb2Mode = True) as device:
    q_rgb = device.getOutputQueue("rgb")
    # Pad detection results are added into the cache, then averaged
    # Start the cache with image center
    cache = [(int(width / 2), int(height / 2))]
    cache_amount = 10

    #preload = cv.imread("actual_data\dji_fly_20230409_190208_596_1681085376047_photo_optimized.jpg", cv.IMREAD_COLOR)

    while True:
        image = get_most_recent_img(q_rgb)
        if image is not None:
            pad_loc = pattern_detection_tick(sift, kp1, des1, image)
            if pad_loc is not None:
                cache.append(pad_loc)
                if len(cache) > cache_amount:
                    cache.pop(0)

            pad_loc = (0, 0)
            for i in cache:
                pad_loc = (
                    pad_loc[0] + i[0],
                    pad_loc[1] + i[1]
                )
            pad_loc = (
                int(pad_loc[0] / len(cache)),
                int(pad_loc[1] / len(cache))
            )

            show_results(image, pad_loc)
        if cv.waitKey(1) == ord('q'):
            break

"""
width = 300
height = 300

input = cv.imread("train2.png")
input = cv.resize(input, (width, height))
input = cv.GaussianBlur(input, (7, 7), cv.BORDER_DEFAULT)
cv.imshow("Input Image Blurred", input)

grey = cv.cvtColor(input, cv.COLOR_BGR2GRAY)
ret, binarized = cv.threshold(grey, 200, 255, cv.THRESH_BINARY)
cv.imshow("Binarized Image", binarized)

average_white = [0, 0]
white_pixels = 0
for x in range(binarized.shape[0]):
    for y in range(binarized.shape[1]):
        if binarized[x, y] == 255:
            average_white[0] += x
            average_white[1] += y
            white_pixels += 1
average_white[0] = int(average_white[0] / white_pixels)
average_white[1] = int(average_white[1] / white_pixels)
# Flip them, idk why
left = average_white[0]
average_white[0] = average_white[1]
average_white[1] = left

print(average_white)

loc = cv.cvtColor(binarized, cv.COLOR_GRAY2BGR)
cv.putText(loc, "A", average_white, cv.FONT_HERSHEY_TRIPLEX, 1.0, (0, 0, 255), 2)
cv.putText(loc, str(average_white), (50, 50), cv.FONT_HERSHEY_TRIPLEX, 1.0, (0, 0, 255), 2)
cv.imshow("A=Payload Location", loc)

# Pause
cv.waitKey(0)
"""