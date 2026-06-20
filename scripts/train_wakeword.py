import os
import sys

try:
    import openwakeword
    from openwakeword.custom_model import train_custom_model
except ImportError as e:
    print(f"ImportError: {e}")
    print("Missing dependencies. Please run: .venv\\Scripts\\python.exe -m pip install openwakeword torch torchvision torchaudio")
    sys.exit(1)

def main():
    print("="*50)
    print("   🧠 MIZUNE WAKE WORD TRAINER 🧠")
    print("="*50)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data", "wakewords")
    output_dir = os.path.join(base_dir, "models", "wakewords")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(data_dir):
        print(f"Error: Could not find data directory at {data_dir}")
        return
        
    # Find all subdirectories in data/wakewords/
    words_to_train = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    if not words_to_train:
        print("No wake word folders found. Please run record_wakeword.py first!")
        return
        
    print(f"Found the following wake words to train: {', '.join(words_to_train)}\n")
    
    for word in words_to_train:
        word_dir = os.path.join(data_dir, word)
        
        # Count wav files
        wav_files = [f for f in os.listdir(word_dir) if f.endswith('.wav')]
        if len(wav_files) == 0:
            print(f"Skipping '{word}' (0 .wav files found)")
            continue
            
        print(f"\n--- Training model for '{word}' ({len(wav_files)} samples) ---")
        
        try:
            # openWakeWord provides an automated training pipeline for few-shot learning
            # This generates a custom .onnx model using your samples + pre-built negative datasets
            model_name = f"{word}_custom"
            
            # The custom model trainer in openwakeword
            # It extracts features from the positive clips and trains a logistic regression classifier on top of the base openWakeWord embedding model
            train_custom_model(
                positive_data=[word_dir],
                output_name=model_name,
                output_dir=output_dir,
                model_name=word
            )
            print(f"✅ Successfully trained {model_name}.onnx!")
            print(f"Saved to: {os.path.join(output_dir, model_name + '.onnx')}")
        except Exception as e:
            print(f"❌ Failed to train '{word}': {e}")
            print("Note: If you run into missing dataset errors, openWakeWord might need to download negative training data on the first run.")

    print("\n" + "="*50)
    print("🎉 ALL DONE!")
    print(f"Your custom wake word models (.onnx) are saved in: {output_dir}")
    print("You can now load these into your voice pipeline!")
    print("="*50)

if __name__ == "__main__":
    main()
