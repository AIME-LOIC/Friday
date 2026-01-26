try:
    import speech_recognition as sr
except ImportError:
    print("Missing dependency: speech_recognition. Install dependencies with:\n  pip install -r requirements.txt")
    raise


r = sr.Recognizer()
# Force a standard 48k sample rate to match Kali's PipeWire
with sr.Microphone(sample_rate=48000) as source:
    print("Mic is OPEN. Calibrating...")
    # Give it a very short window
    r.adjust_for_ambient_noise(source, duration=0.5)
    print("Speak now, sir!")
    
    try:
        audio = r.listen(source, timeout=5)
        print("Got audio! Recognizing...")
        print("You said: " + r.recognize_google(audio))
    except Exception as e:
        print(f"Error: {e}")