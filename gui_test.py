# ...existing code...
import queue
import tkinter as tk
from tkinter import messagebox
import speech_recognition as sr
import traceback
import logging
import os
import time

logging.basicConfig(level=logging.INFO)

def choose_microphone_index(prefer_first=True):
    """Return a microphone index or None. Logs available devices."""
    try:
        names = sr.Microphone.list_microphone_names()
    except Exception:
        logging.exception("Failed to list microphones")
        return None
    logging.info("Available microphones:")
    for i, n in enumerate(names):
        logging.info("  %d: %s", i, n)
    if not names:
        return None
    # prefer a non-loopback device if possible
    if not prefer_first:
        for i, n in enumerate(names):
            if "loop" not in n.lower() and "virtual" not in n.lower():
                return i
    return 0

def _save_audio_for_debug(audio, path="/tmp/friday_last.wav"):
    try:
        data = audio.get_wav_data()
        with open(path, "wb") as f:
            f.write(data)
        logging.info("Saved last audio to %s", path)
    except Exception:
        logging.exception("Failed to save audio for debug")

def callback_handle(recognizer, audio, q):
    """Try recognizers, put results (status, text) into queue."""
    try:
        # primary: Google Web Speech API (online)
        text = recognizer.recognize_google(audio)
        q.put(("ok", text))
        logging.info("Recognized (google): %s", text)
        return
    except sr.UnknownValueError:
        logging.info("Google could not understand audio; saving for debug")
        _save_audio_for_debug(audio)
        # try offline fallback if available
        try:
            text = recognizer.recognize_sphinx(audio)
            q.put(("ok", text + " (sphinx)"))
            logging.info("Recognized (sphinx): %s", text)
            return
        except sr.UnknownValueError:
            q.put(("err", "Could not understand audio"))
            return
        except Exception as e:
            logging.warning("PocketSphinx fallback failed: %s", e)
            q.put(("err", "Could not understand audio"))
            return
    except sr.RequestError as e:
        logging.error("API error: %s", e)
        q.put(("err", f"API error: {e}"))
    except Exception as e:
        logging.exception("Recognition exception")
        _save_audio_for_debug(audio)
        q.put(("err", f"Recognition exception: {e}"))

def start_listener(q, device_index=None, calibrate_duration=3):
    """
    Starts the speech recognition listener in the background.

    Uses a temporary Microphone for ambient noise calibration and passes
    the actual Microphone instance to listen_in_background (which will
    open it in the background thread). Returns a stop function.
    """
    r = sr.Recognizer()
    # tune thresholds for smoother detection
    r.pause_threshold = 0.6
    r.dynamic_energy_threshold = True

    try:
        if device_index is None:
            device_index = choose_microphone_index(prefer_first=False)
        mic = sr.Microphone(device_index=device_index)
    except Exception as e:
        logging.exception("Failed to create Microphone object")
        raise RuntimeError(f"Failed to create Microphone: {e}") from e

    # Calibrate ambient noise using a separate temporary context so we
    # don't enter the same Microphone object that the background thread will.
    try:
        with sr.Microphone(device_index=device_index) as temp_source:
            logging.info("Calibrating ambient noise for %s seconds...", calibrate_duration)
            r.adjust_for_ambient_noise(temp_source, duration=calibrate_duration)
            logging.info("Calibration done; energy_threshold=%s", r.energy_threshold)
    except Exception:
        logging.exception("Ambient noise calibration failed; continuing and attempting to start listener")

    # wrapper that matches listen_in_background signature
    def _callback(recognizer, audio):
        callback_handle(recognizer, audio, q)

    try:
        stop_listening = r.listen_in_background(mic, _callback)
        logging.info("Started background listener on device index %s", device_index)
    except Exception:
        logging.exception("Failed to start background listener")
        raise

    def stop_all(wait_for_stop=False):
        try:
            stop_listening(wait_for_stop=wait_for_stop)
        except Exception:
            logging.exception("Error stopping background listener")

    return stop_all

def main():
    q = queue.Queue()

    root = tk.Tk()
    root.title("Friday test listener")
    label = tk.Label(root, text="Waiting for speech...", width=60)
    label.pack(padx=10, pady=10)

    # try to start listener and show dialog on failure
    try:
        device_index = choose_microphone_index(prefer_first=False)
        stop = start_listener(q, device_index=device_index, calibrate_duration=3)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error("Listener startup failed: %s\n%s", e, tb)
        messagebox.showerror("Microphone error", f"Failed to start listener: {e}\nSee terminal for details.")
        label.config(text=f"Error starting listener: {e}")
        stop = None

    def poll_queue():
        try:
            status, payload = q.get_nowait()
        except queue.Empty:
            root.after(150, poll_queue)
            return
        if status == "ok":
            label.config(text="Heard: " + payload)
        else:
            label.config(text="Error: " + payload)
        root.after(150, poll_queue)

    root.after(150, poll_queue)

    def on_close():
        try:
            if callable(stop):
                stop(wait_for_stop=False)
        except Exception:
            logging.exception("Error stopping listener")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
# ...existing code...