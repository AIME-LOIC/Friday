import cv2

cap = cv2.VideoCapture(0)  # try 0, then 1, then 2 if needed
if not cap.isOpened():
    print("Camera index 0 cannot be opened")
else:
    print("Camera 0 opened OK")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame")
            break
        cv2.imshow("Camera test", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
            break

cap.release()
cv2.destroyAllWindows()