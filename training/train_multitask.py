import argparse
import os

import tensorflow as tf

from .dataset import build_dataset
from .labels import ACTIVITY_LABELS, EMOTION_LABELS, IDENTITY_LABELS
from .model import build_multitask_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to dataset root")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--out", default="models/mizune_multitask")
    args = parser.parse_args()

    tf.keras.mixed_precision.set_global_policy("mixed_float16")

    ds = build_dataset(
        dataset_path=args.dataset,
        batch_size=args.batch,
    )

    model = build_multitask_model(
        activity_classes=len(ACTIVITY_LABELS),
        emotion_classes=len(EMOTION_LABELS),
        identity_classes=len(IDENTITY_LABELS),
    )

    losses = {
        "activity": "categorical_crossentropy",
        "emotion": "categorical_crossentropy",
        "identity": "binary_crossentropy" if len(IDENTITY_LABELS) == 2 else "categorical_crossentropy",
    }

    metrics = {
        "activity": ["accuracy"],
        "emotion": ["accuracy"],
        "identity": ["accuracy"],
    }

    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss=losses,
        metrics=metrics,
    )

    os.makedirs(args.out, exist_ok=True)
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(args.out, "checkpoint"),
            save_best_only=True,
            monitor="loss",
        )
    ]

    model.fit(ds, epochs=args.epochs, callbacks=callbacks)
    model.save(args.out)


if __name__ == "__main__":
    main()
