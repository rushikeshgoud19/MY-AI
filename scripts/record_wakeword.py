import os
import sys
import time
import queue
import argparse
import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    print("Missing dependencies. Please run: pip install sounddevice soundfile numpy")
    sys.exit(1)

# openWakeWord expects 16kHz mono audio
SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 2.0  # 2 seconds per sample is usually plenty for a wake word

def record_sample(filename):
    """Records a single audio sample and saves it to a file."""
    print(f"\n🎙️  Recording started... SPEAK NOW! ({RECORD_SECONDS}s)")
    
    # Record audio
    recording = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), 
                       samplerate=SAMPLE_RATE, 
                       channels=CHANNELS, 
                       dtype='float32')
    
    # Wait until recording is finished
    sd.wait()
    
    # Save to file
    sf.write(filename, recording, SAMPLE_RATE)
    print(f"✅ Saved to {filename}")

def main():
    print("="*50)
    print("   🎙️ MIZUNE WAKE WORD DATA COLLECTOR 🎙️")
    print("="*50)
    
    word = input("\nEnter the wake word you want to train (e.g., Mizu, Mizune, Baka): ").strip()
    if not word:
        print("Wake word cannot be empty!")
        return

    try:
        num_samples = int(input("How many samples do you want to record? (Recommend 50+): ").strip() or "50")
    except ValueError:
        num_samples = 50

    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "wakewords", word.lower())
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nCreating dataset in: {os.path.abspath(output_dir)}")
    print(f"We will record {num_samples} samples of you saying '{word}'.")
    print("Try to vary your tone, speed, and distance from the microphone slightly.\n")
    
    input("Press ENTER when you are ready to begin...")

    for i in range(1, num_samples + 1):
        filename = os.path.join(output_dir, f"{word.lower()}_{i:03d}.wav")
        
        print(f"\n--- Sample {i}/{num_samples} ---")
        input("Press ENTER to record (or Ctrl+C to quit)...")
        
        record_sample(filename)
        
    print("\n" + "="*50)
    print(f"🎉 SUCCESS! Collected {num_samples} samples of '{word}'.")
    print(f"Directory: {os.path.abspath(output_dir)}")
    print("="*50)
    print("\nNext step: Run the openWakeWord training script on this directory.")

if __name__ == "__main__":
    main()
