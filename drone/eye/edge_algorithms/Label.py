import cv2 as cv

markers = {
    "medkit": cv.imread("MedKit.png"),
    "bottle": cv.imread("Bottle.png"),
    "smores": cv.imread("Smores.png")
}

#feature detector object
detector = cv.ORB_create()

matcher = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)

camera = cv.VideoCapture(0)

while True:
    ret, frame = camera.read()

    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    most_similar_label = "unknown" 
    
    max_similarity_score = 0
    for label, image in markers.items():
        # Get the descriptors from the marker
        key_image, des_image = detector.detectAndCompute(image, None)

        # Get the descriptors from the grayscale of the frame
        key_gray, des_gray = detector.detectAndCompute(gray, None)

        # Match the descriptors from the marker with the descriptors from the current frame
        matches = matcher.match(des_image, des_gray)

        # Count the number of good matches
        good_matches = len([m for m in matches if m.distance < 50])

        if good_matches > max_similarity_score:
            max_similarity_score = good_matches
            most_similar_label = label

    
    cv.putText(frame, most_similar_label, (50, 50), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv.imshow('Result', frame)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv.destroyAllWindows()