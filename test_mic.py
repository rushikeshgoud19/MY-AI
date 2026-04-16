"""Quick mic diagnostic script for Mizune."""
import sounddevice as sd
import numpy as np
import wave
import io
import speech_recognition as sr

# 1. Show audio devices
print("=" * 50)
print("AUDIO DEVICE INFO")
print("=" * 50)
print(f"Default device pair: {sd.default.device}")

try:
    info = sd.query_devices(sd.default.device[0], "input")
    print(f"Input device: {info['name']}")
    print(f"Default sample rate: {info['default_samplerate']}")
    print(f"Max input channels: {info['max_input_channels']}")
except Exception as e:
    print(f"Error querying default input: {e}")

print("\nAll input-capable devices:")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"  [{i}] {d['name']} (channels={d['max_input_channels']}, rate={d['default_samplerate']})")

# 2. Record a short clip and measure levels
print("\n" + "=" * 50)
print("RECORDING 3 SECONDS... Speak now!")
print("=" * 50)

try:
    sr_val = int(sd.query_devices(sd.default.device[0], "input")["default_samplerate"])
except:
    sr_val = 44100

audio = sd.rec(int(3 * sr_val), samplerate=sr_val, channels=1, dtype="int16")
sd.wait()

peak = np.max(np.abs(audio))
rms = int(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
print(f"Peak amplitude: {peak} / 32768")
print(f"RMS level: {rms}")
print(f"Sample rate used: {sr_val}")

if peak < 50:
    print(">>> WARNING: Audio is basically SILENT. Wrong mic or mic is muted!")
elif peak < 500:
    print(">>> WARNING: Audio is very quiet. Mic volume may be too low.")
else:
    print(">>> Audio level looks OK.")

# 3. Try STT
print("\n" + "=" * 50)
print("TESTING SPEECH RECOGNITION...")
print("=" * 50)

wav_buf = io.BytesIO()
with wave.open(wav_buf, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr_val)
    wf.writeframes(audio.tobytes())
wav_buf.seek(0)

recognizer = sr.Recognizer()
with sr.AudioFile(wav_buf) as source:
    audio_data = recognizer.record(source)

try:
    text = recognizer.recognize_google(audio_data, language="en-IN")
    print(f"Recognized: '{text}'")
except sr.UnknownValueError:
    print("FAILED: Could not understand audio")
    print("Trying with different language setting (en-US)...")
    wav_buf.seek(0)
    with sr.AudioFile(wav_buf) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data, language="en-US")
        print(f"Recognized (en-US): '{text}'")
    except sr.UnknownValueError:
        print("FAILED with en-US too. Mic issue is likely hardware/driver level.")
except sr.RequestError as e:
    print(f"API Error: {e}")
