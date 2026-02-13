import threading
import time

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

    def __init__(
        self,
        on_open_hand=None,
        on_closed_fist=None,
        on_two_fingers=None,  # backward-compat (treated like hold)
        on_open_palm=None,
        on_two_fingers_tap=None,
        on_two_fingers_hold=None,
        on_detection=None,  # (fingers_up, pointer_xy) -> None
        on_pointer=None,  # (x_norm, y_norm) -> None
        *,
        camera_index: int = 0,
        start_immediately: bool = True,
        cooldown_s: float = 1.2,
        two_finger_hold_s: float = 1.0,
        on_status=None,
        dispatcher=None,
        show_preview: bool = False,
        model_path: str | None = None,
    ):
        self.on_open_hand = on_open_hand
        self.on_closed_fist = on_closed_fist
        self.on_two_fingers = on_two_fingers
        self.on_open_palm = on_open_palm
        self.on_two_fingers_tap = on_two_fingers_tap
        self.on_two_fingers_hold = on_two_fingers_hold
        self.on_detection = on_detection
        self.on_pointer = on_pointer
        self.camera_index = camera_index
        self.cooldown_s = max(0.0, float(cooldown_s))
        self.two_finger_hold_s = max(0.1, float(two_finger_hold_s))
        self.on_status = on_status
        self.dispatcher = dispatcher
        self.show_preview = show_preview
        self.model_path = model_path
        self._stop = threading.Event()
        self._thread = None

        if not cv2 or not mp:
            # Dependencies not available – no-op controller
            self._emit_status("Gesture controller disabled (missing cv2/mediapipe).")
            return

        if start_immediately:
            self.start()

    def start(self):
        if not cv2 or not mp:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._emit_status(f"Gesture controller started (camera {self.camera_index}).")

    def stop(self):
        self._stop.set()
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
        except Exception:
            pass
        self._emit_status("Gesture controller stopped.")

    # --- Internal helpers -------------------------------------------------

    def _dispatch(self, fn):
        if not callable(fn):
            return
        if callable(self.dispatcher):
            try:
                self.dispatcher(fn)
                return
            except Exception:
                pass
        try:
            fn()
        except Exception:
            pass

    def _emit_status(self, message: str):
        if not callable(self.on_status):
            return
        msg = str(message)
        if callable(self.dispatcher):
            try:
                self.dispatcher(lambda: self.on_status(msg))
                return
            except Exception:
                pass
        try:
            self.on_status(msg)
        except Exception:
            pass

    def _run(self):
        if not cv2 or not mp:
            return

        cap = cv2.VideoCapture(int(self.camera_index))
        if not cap.isOpened():
            # Camera not available
            self._emit_status(f"Camera {self.camera_index} could not be opened.")
            return

        self._emit_status(f"Camera {self.camera_index} opened.")
        use_solutions = hasattr(mp, "solutions")
        hands = None
        landmarker = None
        running_mode_video = None

        if use_solutions:
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )
            self._emit_status("Gesture backend: mp.solutions.hands")
        else:
            # Fallback to MediaPipe Tasks API (requires model file).
            try:
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision
            except Exception as e:
                self._emit_status(f"Gesture controller disabled (tasks import failed): {e}")
                cap.release()
                return

            model_path = self.model_path
            if not model_path:
                self._emit_status(
                    "Gesture controller disabled (no model_path; expected hand_landmarker.task)."
                )
                cap.release()
                return

            try:
                base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.VIDEO,
                    num_hands=1,
                    min_hand_detection_confidence=0.6,
                    min_hand_presence_confidence=0.6,
                    min_tracking_confidence=0.6,
                )
                landmarker = vision.HandLandmarker.create_from_options(options)
                running_mode_video = vision.RunningMode.VIDEO
                self._emit_status("Gesture backend: mediapipe.tasks HandLandmarker")
            except Exception as e:
                self._emit_status(f"Gesture controller disabled (model load failed): {e}")
                cap.release()
                return

        last_action = 0.0
        two_start = None
        two_hold_fired = False

        try:
            while not self._stop.is_set():
                ret, frame = cap.read()
                if not ret:
                    self._emit_status("Camera read failed.")
                    break

                # Mirror like a selfie camera
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                landmarks = None
                handedness = None
                if hands is not None:
                    result = hands.process(rgb)
                    if result.multi_hand_landmarks:
                        landmarks = result.multi_hand_landmarks[0].landmark
                        try:
                            if getattr(result, "multi_handedness", None):
                                handedness = (
                                    result.multi_handedness[0]
                                    .classification[0]
                                    .label
                                )
                        except Exception:
                            handedness = None
                elif landmarker is not None:
                    try:
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                        ts_ms = int(time.time() * 1000)
                        result = landmarker.detect_for_video(mp_image, ts_ms)
                        if getattr(result, "hand_landmarks", None):
                            landmarks = result.hand_landmarks[0]
                        try:
                            # Best-effort: Tasks API may expose handedness differently across versions.
                            handed = getattr(result, "handedness", None) or getattr(result, "handednesses", None)
                            if handed and handed[0] and handed[0][0]:
                                handedness = getattr(handed[0][0], "category_name", None) or getattr(handed[0][0], "display_name", None)
                        except Exception:
                            handedness = None
                    except Exception:
                        landmarks = None

                if landmarks:
                    # Finger counting:
                    # - Index/middle/ring/pinky: tip above PIP => extended
                    # - Thumb: best-effort heuristic
                    finger_tips = [8, 12, 16, 20]
                    finger_pips = [6, 10, 14, 18]
                    fingers_up = 0

                    for tip, pip in zip(finger_tips, finger_pips):
                        if landmarks[tip].y < landmarks[pip].y:
                            fingers_up += 1

                    thumb_extended = False
                    try:
                        # Use a magnitude check as a fallback when handedness is unknown.
                        dx = abs(landmarks[4].x - landmarks[3].x)
                        thumb_extended = dx > 0.04
                        if handedness:
                            h = str(handedness).lower()
                            # With selfie-mirror flip, handedness may be unreliable; keep magnitude gate.
                            if "right" in h:
                                thumb_extended = thumb_extended and (landmarks[4].x < landmarks[3].x)
                            elif "left" in h:
                                thumb_extended = thumb_extended and (landmarks[4].x > landmarks[3].x)
                    except Exception:
                        thumb_extended = False

                    if thumb_extended:
                        fingers_up += 1

                    pointer_xy = None
                    try:
                        pointer_xy = (float(landmarks[8].x), float(landmarks[8].y))
                    except Exception:
                        pointer_xy = None

                    if pointer_xy and callable(self.on_pointer):
                        self._dispatch(lambda p=pointer_xy: self.on_pointer(p[0], p[1]))

                    now = time.time()
                    if callable(self.on_detection):
                        self._dispatch(lambda f=fingers_up, p=pointer_xy: self.on_detection(f, p))

                    # 2-finger tap vs hold (hold can be used for panel switching)
                    if fingers_up == 2:
                        if two_start is None:
                            two_start = now
                            two_hold_fired = False
                        if not two_hold_fired and (now - two_start) >= self.two_finger_hold_s:
                            two_hold_fired = True
                            if callable(self.on_two_fingers_hold):
                                self._dispatch(self.on_two_fingers_hold)
                            elif callable(self.on_two_fingers):
                                self._dispatch(self.on_two_fingers)
                    else:
                        if two_start is not None:
                            duration = now - two_start
                            if duration < self.two_finger_hold_s and callable(self.on_two_fingers_tap):
                                self._dispatch(self.on_two_fingers_tap)
                        two_start = None
                        two_hold_fired = False

                    # Cooldown-gated actions
                    if self.cooldown_s and (now - last_action) < self.cooldown_s:
                        pass
                    else:
                        if fingers_up == 3:
                            last_action = now
                            self._dispatch(self.on_open_hand)
                        elif fingers_up >= 4:
                            last_action = now
                            if callable(self.on_open_palm):
                                self._dispatch(self.on_open_palm)
                        elif fingers_up == 0:
                            last_action = now
                            self._dispatch(self.on_closed_fist)

                if self.show_preview:
                    try:
                        cv2.imshow("FRIDAY Gesture Camera", frame)
                        if cv2.waitKey(1) & 0xFF == 27:
                            break
                    except Exception:
                        pass
                else:
                    time.sleep(0.01)
        finally:
            try:
                if hands is not None:
                    hands.close()
            except Exception:
                pass
            try:
                if landmarker is not None:
                    landmarker.close()
            except Exception:
                pass
            cap.release()
            try:
                if self.show_preview:
                    cv2.destroyAllWindows()
            except Exception:
                pass
