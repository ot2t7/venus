#type: ignore

from pathlib import Path
import sys
#import cv2
import depthai as dai
import numpy as np
import time

nnPath = "./assets/detection_model.blob"

labelMap = [
    "bottle_dropoff",
    "bottle_pickup",
    "medkit_dropoff",
    "medkit_pickup",
    "smores_dropoff",
    "smores_pickup",
    "pad_center"
]

syncNN = True

# Create pipeline
pipeline = dai.Pipeline()

# Define sources and outputs
camRgb = pipeline.create(dai.node.ColorCamera)
detectionNetwork = pipeline.create(dai.node.YoloDetectionNetwork)
xoutRgb = pipeline.create(dai.node.XLinkOut)
nnOut = pipeline.create(dai.node.XLinkOut)

xoutRgb.setStreamName("rgb")
nnOut.setStreamName("nn")

# Properties
camRgb.setPreviewKeepAspectRatio(False)
camRgb.setPreviewSize(416, 416)
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
camRgb.setInterleaved(False)
camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
camRgb.setFps(40)

# Network specific settings
detectionNetwork.setConfidenceThreshold(0.5)
detectionNetwork.setNumClasses(7)
detectionNetwork.setCoordinateSize(4)
detectionNetwork.setAnchors([
                10.0,
                13.0,
                16.0,
                30.0,
                33.0,
                23.0,
                30.0,
                61.0,
                62.0,
                45.0,
                59.0,
                119.0,
                116.0,
                90.0,
                156.0,
                198.0,
                373.0,
                326.0
])
detectionNetwork.setAnchorMasks(
    {
        "side52": [0, 1, 2], 
        "side26": [3, 4, 5], 
        "side13": [6, 7, 8]
    }
)
detectionNetwork.setIouThreshold(0.5)
detectionNetwork.setBlobPath(nnPath)
detectionNetwork.setNumInferenceThreads(2)
detectionNetwork.input.setBlocking(False)

# Linking
camRgb.preview.link(detectionNetwork.input)
if syncNN:
    detectionNetwork.passthrough.link(xoutRgb.input)
else:
    camRgb.preview.link(xoutRgb.input)

detectionNetwork.out.link(nnOut.input)

# Camera control
controlIn = pipeline.create(dai.node.XLinkIn)
controlIn.setStreamName("control")
controlIn.out.link(camRgb.inputControl)

# Connect to device and start pipeline
with dai.Device(pipeline, usb2Mode=False) as device:
    qControl = device.getInputQueue(name="control")
    cc = dai.CameraControl()
    cc.setManualExposure(1500, 100)
    #qControl.send(cc)

    # Output queues will be used to get the rgb frames and nn data from the outputs defined above
    qRgb = device.getOutputQueue(name="rgb", maxSize=1, blocking=False)
    qDet = device.getOutputQueue(name="nn", maxSize=1, blocking=False)

    frame = None
    detections = []
    startTime = time.monotonic()
    counter = 0
    color2 = (255, 255, 255)

    # nn data, being the bounding box locations, are in <0..1> range - they need to be normalized with frame width/height
    def frameNorm(frame, bbox):
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

    def displayFrame(name, frame):
        color = (255, 0, 0)
        output = "Pads in frame: "
        for detection in detections:
            """
            bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
            cv2.putText(frame, labelMap[detection.label], (bbox[0] + 10, bbox[1] + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
            cv2.putText(frame, f"{int(detection.confidence * 100)}%", (bbox[0] + 10, bbox[1] + 40), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            """

            output += (labelMap[detection.label] + " ")
            
        # Show the frame
        print(output)
        #cv2.imshow(name, frame)

    while True:
        if syncNN:
            inRgb = qRgb.get()
            inDet = qDet.get()
        else:
            inRgb = qRgb.tryGet()
            inDet = qDet.tryGet()

        if inRgb is not None:
            frame = "trololo" #inRgb.getCvFrame()
            #cv2.putText(frame, "NN fps: {:.2f}".format(counter / (time.monotonic() - startTime)),
                        #(2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, color2)

        if inDet is not None:
            detections = inDet.detections
            counter += 1

        if frame is not None:
            displayFrame("rgb", frame)

        #if cv2.waitKey(1) == ord('q'):
            #break