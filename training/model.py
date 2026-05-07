import tensorflow as tf


def build_multitask_model(
    activity_classes: int,
    emotion_classes: int,
    identity_classes: int,
    camera_size: int = 160,
    screen_size: int = 224,
) -> tf.keras.Model:
    camera_input = tf.keras.Input(shape=(camera_size, camera_size, 3), name="camera")
    screen_input = tf.keras.Input(shape=(screen_size, screen_size, 3), name="screen")
    time_input = tf.keras.Input(shape=(4,), name="time_features")

    camera_base = tf.keras.applications.MobileNetV3Small(
        input_shape=(camera_size, camera_size, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )
    screen_base = tf.keras.applications.MobileNetV3Small(
        input_shape=(screen_size, screen_size, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )

    camera_feat = camera_base(camera_input)
    screen_feat = screen_base(screen_input)

    fused = tf.keras.layers.Concatenate(name="fusion")([
        camera_feat,
        screen_feat,
        time_input,
    ])
    fused = tf.keras.layers.Dense(256, activation="relu")(fused)
    fused = tf.keras.layers.Dropout(0.3)(fused)

    activity_head = tf.keras.layers.Dense(
        activity_classes, activation="softmax", name="activity"
    )(fused)
    emotion_head = tf.keras.layers.Dense(
        emotion_classes, activation="softmax", name="emotion"
    )(fused)

    if identity_classes == 2:
        identity_head = tf.keras.layers.Dense(1, activation="sigmoid", name="identity")(fused)
    else:
        identity_head = tf.keras.layers.Dense(
            identity_classes, activation="softmax", name="identity"
        )(fused)

    return tf.keras.Model(
        inputs={
            "camera": camera_input,
            "screen": screen_input,
            "time_features": time_input,
        },
        outputs={
            "activity": activity_head,
            "emotion": emotion_head,
            "identity": identity_head,
        },
        name="mizune_multitask",
    )
