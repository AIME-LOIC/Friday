import threading

# Optional heavy imports – we don't want the whole app to crash if missing
try:
    import cv2
    import mediapipe as mp
except Exception:
    cv2 = None
    mp = None


class GestureController:
    """
    Lightweight hand-gesture controller using OpenCV + MediaPipe.

    - Runs in its own thread so it won't block the GUI.
    - Detects a very small set of gestures and invokes callbacks:
        * open hand  -> on_open_hand()
        * closed fist -> on_closed_fist()
    - If OpenCV/MediaPipe are not installed or camera fails, it silently disables itself.
    """

    def __init__(self, on_open_hand=None, on_closed_fist=None):
        self.on_open_hand = on_open_hand
        self.on_closed_fist = on_closed_fist
        self._stop = threading.Event()

        if not cv2 or not mp:
            # Dependencies not available – no-op controller
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    # --- Internal helpers -------------------------------------------------

    def _run(self):
        if not cv2 or not mp:
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            # Camera not available
            return

        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        try:
            while not self._stop.is_set():
                ret, frame = cap.read()
                if not ret:
                    break

                # Mirror like a selfie camera
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)

                if result.multi_hand_landmarks:
                    lm = result.multi_hand_landmarks[0]
                    # Simple heuristic: count "extended" fingers based on y-position
                    tip_ids = [4, 8, 12, 16, 20]
                    fingers_up = 0
                    # Use wrist as approximate palm reference
                    wrist_y = lm.landmark[0].y
                    for tid in tip_ids[1:]:  # ignore thumb for simplicity
                        if lm.landmark[tid].y < wrist_y:  # above wrist -> extended
                            fingers_up += 1

                    if fingers_up >= 3:
                        # Open hand
                        if callable(self.on_open_hand):
                            self.on_open_hand()
                    elif fingers_up == 0:
                        # Closed fist
                        if callable(self.on_closed_fist):
                            self.on_closed_fist()

                # Very light wait so we don't burn CPU
                if cv2.waitKey(10) & 0xFF == 27:  # ESC to stop debug loop if window visible
                    break
        finally:
            try:
                hands.close()
            except Exception:
                pass
            cap.release()
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

