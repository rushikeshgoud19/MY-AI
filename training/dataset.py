import json
import os
from typing import Iterable, Tuple

import tensorflow as tf

from .labels import ACTIVITY_LABELS, EMOTION_LABELS, IDENTITY_LABELS


def _label_to_index(label: str, label_list: list[str]) -> int:
    try:
        return label_list.index(label)
    except ValueError:
        return -1


def load_records(meta_dir: str) -> list[dict]:
    records = []
    if not os.path.isdir(meta_dir):
        return records
    for name in sorted(os.listdir(meta_dir)):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(meta_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    return records


def _parse_record(
    record: dict,
    camera_size: int,
    screen_size: int,
) -> Tuple[dict, dict]:
    camera_path = record.get("camera_path", "")
    screen_path = record.get("screen_path", "")

    camera_bytes = tf.io.read_file(camera_path)
    camera_img = tf.image.decode_jpeg(camera_bytes, channels=3)
    camera_img = tf.image.resize(camera_img, (camera_size, camera_size))
    camera_img = tf.keras.applications.mobilenet_v3.preprocess_input(camera_img)

    screen_bytes = tf.io.read_file(screen_path)
    screen_img = tf.image.decode_png(screen_bytes, channels=3)
    screen_img = tf.image.resize(screen_img, (screen_size, screen_size))
    screen_img = tf.keras.applications.mobilenet_v3.preprocess_input(screen_img)

    time_features = tf.convert_to_tensor([
        record.get("hour_sin", 0.0),
        record.get("hour_cos", 0.0),
        record.get("weekday_sin", 0.0),
        record.get("weekday_cos", 0.0),
    ], dtype=tf.float32)

    activity = _label_to_index(record.get("activity_label", ""), ACTIVITY_LABELS)
    emotion = _label_to_index(record.get("emotion_label", ""), EMOTION_LABELS)
    identity = _label_to_index(record.get("identity_label", ""), IDENTITY_LABELS)

    activity_label = tf.one_hot(activity, len(ACTIVITY_LABELS))
    emotion_label = tf.one_hot(emotion, len(EMOTION_LABELS))
    if len(IDENTITY_LABELS) == 2:
        identity_label = tf.cast(identity == 0, tf.float32)
    else:
        identity_label = tf.one_hot(identity, len(IDENTITY_LABELS))

    inputs = {
        "camera": camera_img,
        "screen": screen_img,
        "time_features": time_features,
    }
    labels = {
        "activity": activity_label,
        "emotion": emotion_label,
        "identity": identity_label,
    }
    return inputs, labels


def build_dataset(
    dataset_path: str,
    batch_size: int = 16,
    camera_size: int = 160,
    screen_size: int = 224,
    shuffle: bool = True,
    filter_unlabeled: bool = True,
) -> tf.data.Dataset:
    records = load_records(os.path.join(dataset_path, "meta"))

    if filter_unlabeled:
        records = [
            r for r in records
            if r.get("activity_label") not in ("", "unlabeled")
            and r.get("emotion_label") not in ("", "unlabeled")
            and r.get("identity_label") not in ("", "unlabeled")
        ]

    def gen() -> Iterable[dict]:
        for r in records:
            if not r.get("camera_path") or not r.get("screen_path"):
                continue
            if not os.path.exists(r.get("camera_path")) or not os.path.exists(r.get("screen_path")):
                continue
            yield {
                "camera_path": r.get("camera_path", ""),
                "screen_path": r.get("screen_path", ""),
                "hour_sin": float(r.get("hour_sin", 0.0)),
                "hour_cos": float(r.get("hour_cos", 0.0)),
                "weekday_sin": float(r.get("weekday_sin", 0.0)),
                "weekday_cos": float(r.get("weekday_cos", 0.0)),
                "activity_label": r.get("activity_label", ""),
                "emotion_label": r.get("emotion_label", ""),
                "identity_label": r.get("identity_label", ""),
            }

    ds = tf.data.Dataset.from_generator(
        gen,
        output_signature={
            "camera_path": tf.TensorSpec(shape=(), dtype=tf.string),
            "screen_path": tf.TensorSpec(shape=(), dtype=tf.string),
            "hour_sin": tf.TensorSpec(shape=(), dtype=tf.float32),
            "hour_cos": tf.TensorSpec(shape=(), dtype=tf.float32),
            "weekday_sin": tf.TensorSpec(shape=(), dtype=tf.float32),
            "weekday_cos": tf.TensorSpec(shape=(), dtype=tf.float32),
            "activity_label": tf.TensorSpec(shape=(), dtype=tf.string),
            "emotion_label": tf.TensorSpec(shape=(), dtype=tf.string),
            "identity_label": tf.TensorSpec(shape=(), dtype=tf.string),
        },
    )

    def _map(record):
        return _parse_record(record, camera_size, screen_size)

    if shuffle:
        ds = ds.shuffle(buffer_size=min(2048, max(64, len(records))))

    ds = ds.map(_map, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds
