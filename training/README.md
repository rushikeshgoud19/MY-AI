# Training Pipeline

This folder contains the multi-task TensorFlow training pipeline for:
- Activity classification (screen)
- Emotion classification (camera)
- Identity classification (master vs other)

## Quick Start

1) Collect data in the background (server runs the collector).
2) Label your samples in dataset/meta/*.jsonl.
3) Train:

```bash
python -m training.train_multitask --dataset "C:\Users\rushi\OneDrive\Desktop\my Ai\dataset" --epochs 10 --batch 16
```

## Notes
- Labels live in training/labels.py.
- Model uses MobileNetV3Small for both camera and screen streams.
- Time-of-day features are used as 4D inputs (sin/cos).