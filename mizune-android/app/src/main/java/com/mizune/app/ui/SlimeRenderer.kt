package com.mizune.app.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.input.pointer.PointerId
import androidx.compose.ui.input.pointer.PointerEvent
import androidx.compose.ui.input.pointer.pointerInput
import kotlinx.coroutines.launch

// ═══════════════════════════════════════════════════════════════════
// 1.  DATA MODELS & SHAPE SPECIFICATIONS
// ═══════════════════════════════════════════════════════════════════

enum class SlimeEmotion {
    CALM, HAPPY, EXCITED, ANGRY, SAD, PATTED, PLAYFUL, SPEAKING, THINKING
}

enum class SlimeVisualState { Happy, Sleeping, Angry, Patted, Sad }

/** A single cubic bezier segment. */
private data class Cubic(val p0: Offset, val p1: Offset, val p2: Offset, val p3: Offset)

/** A shape is an ordered list of cubic segments that form a closed loop. */
private data class ShapeSpec(val segments: List<Cubic>)

/** All shapes share exactly 4 cubic segments so we can lerp them perfectly. */
private val HappyShape = ShapeSpec(
    listOf(
        Cubic(Offset(100f, 20f), Offset(150f, 20f), Offset(195f, 70f), Offset(190f, 120f)),
        Cubic(Offset(190f, 120f), Offset(185f, 170f), Offset(160f, 198f), Offset(100f, 198f)),
        Cubic(Offset(100f, 198f), Offset(40f, 198f), Offset(15f, 170f), Offset(10f, 120f)),
        Cubic(Offset(10f, 120f), Offset(5f, 70f), Offset(50f, 20f), Offset(100f, 20f))
    )
)

private val SleepingShape = ShapeSpec(
    listOf(
        Cubic(Offset(100f, 85f), Offset(155f, 85f), Offset(195f, 100f), Offset(195f, 125f)),
        Cubic(Offset(195f, 125f), Offset(195f, 148f), Offset(165f, 158f), Offset(100f, 158f)),
        Cubic(Offset(100f, 158f), Offset(35f, 158f), Offset(5f, 148f), Offset(5f, 125f)),
        Cubic(Offset(5f, 125f), Offset(5f, 100f), Offset(45f, 85f), Offset(100f, 85f))
    )
)

private val AngryShape = ShapeSpec(
    listOf(
        Cubic(Offset(100f, 8f), Offset(142f, 8f), Offset(180f, 48f), Offset(185f, 98f)),
        Cubic(Offset(185f, 98f), Offset(190f, 148f), Offset(168f, 190f), Offset(100f, 190f)),
        Cubic(Offset(100f, 190f), Offset(32f, 190f), Offset(10f, 148f), Offset(15f, 98f)),
        Cubic(Offset(15f, 98f), Offset(20f, 48f), Offset(58f, 8f), Offset(100f, 8f))
    )
)

private val PattedShape = ShapeSpec(
    listOf(
        Cubic(Offset(100f, 35f), Offset(152f, 35f), Offset(192f, 75f), Offset(188f, 125f)),
        Cubic(Offset(188f, 125f), Offset(184f, 175f), Offset(158f, 195f), Offset(100f, 195f)),
        Cubic(Offset(100f, 195f), Offset(42f, 195f), Offset(16f, 175f), Offset(12f, 125f)),
        Cubic(Offset(12f, 125f), Offset(8f, 75f), Offset(48f, 35f), Offset(100f, 35f))
    )
)

private val SadShape = ShapeSpec(
    listOf(
        Cubic(Offset(100f, 30f), Offset(145f, 40f), Offset(185f, 80f), Offset(185f, 130f)),
        Cubic(Offset(185f, 130f), Offset(180f, 175f), Offset(155f, 200f), Offset(100f, 200f)),
        Cubic(Offset(100f, 200f), Offset(45f, 200f), Offset(20f, 175f), Offset(15f, 130f)),
        Cubic(Offset(15f, 130f), Offset(15f, 80f), Offset(55f, 40f), Offset(100f, 30f))
    )
)

/** Linearly interpolate between two offsets. */
private fun lerp(a: Offset, b: Offset, t: Float) = Offset(
    a.x + (b.x - a.x) * t,
    a.y + (b.y - a.y) * t
)

/** Linearly interpolate every control point of two shapes. */
private fun lerpShape(from: ShapeSpec, to: ShapeSpec, t: Float): ShapeSpec =
    ShapeSpec(from.segments.mapIndexed { i, seg ->
        val o = to.segments[i]
        Cubic(
            lerp(seg.p0, o.p0, t), lerp(seg.p1, o.p1, t),
            lerp(seg.p2, o.p2, t), lerp(seg.p3, o.p3, t)
        )
    })

/** Build an actual Compose Path from a spec. */
private fun buildPath(spec: ShapeSpec): Path = Path().apply {
    val first = spec.segments.first()
    moveTo(first.p0.x, first.p0.y)
    spec.segments.forEach { cubicTo(it.p1.x, it.p1.y, it.p2.x, it.p2.y, it.p3.x, it.p3.y) }
    close()
}

// ═══════════════════════════════════════════════════════════════════
// 2.  PHYSICS & GESTURE INFRASTRUCTURE
// ═══════════════════════════════════════════════════════════════════

/** Per-pointer tracking data including a short history for fling velocity. */
private data class PointerTrack(
    val downPos: Offset,
    var current: Offset,
    var prev: Offset,
    val downTime: Long,
    val history: ArrayDeque<Pair<Long, Offset>> = ArrayDeque()
) {
    fun addHistory(time: Long, pos: Offset) {
        history.addLast(time to pos)
        while (history.size > 6) history.removeFirst()
    }

    /** Pixels per second. */
    val velocity: Float
        get() {
            if (history.size < 2) return 0f
            val (t1, p1) = history.first()
            val (t2, p2) = history.last()
            val dt = (t2 - t1) / 1000f
            return if (dt > 0.001f) (p2 - p1).getDistance() / dt else 0f
        }
}

/** A single heart particle emitted while petting. */
private data class HeartParticle(
    val x: Float,
    val y: Float,
    val drift: Float,
    val alpha: Animatable<Float, AnimationVector1D>,
    val offsetY: Animatable<Float, AnimationVector1D>
)

/** Holds the from→to state for smooth path morphing. */
private class MorphState {
    var fromSpec: ShapeSpec = HappyShape
    var toSpec: ShapeSpec = HappyShape
    val progress = Animatable(0f)
}

/** Selects spring physics based on the current mood. */
@Composable
private fun rememberMoodSpring(emotion: SlimeVisualState): SpringSpec<Offset> = remember(emotion) {
    when (emotion) {
        SlimeVisualState.Happy, SlimeVisualState.Patted -> spring(
            dampingRatio = 0.3f,
            stiffness = Spring.StiffnessLow
        )
        SlimeVisualState.Sleeping, SlimeVisualState.Sad -> spring(
            dampingRatio = 0.9f,
            stiffness = Spring.StiffnessVeryLow
        )
        SlimeVisualState.Angry -> spring(
            dampingRatio = 0.5f,
            stiffness = Spring.StiffnessHigh
        )
    }
}

// ═══════════════════════════════════════════════════════════════════
// 3.  THE SLIME RENDERER
// ═══════════════════════════════════════════════════════════════════

@Composable
fun SlimeRenderer(
    emotion: SlimeEmotion,
    isRecording: Boolean = false,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    
    // Map App Emotion to Visual State
    val baseVisualState = when (emotion) {
        SlimeEmotion.ANGRY -> SlimeVisualState.Angry
        SlimeEmotion.SAD -> SlimeVisualState.Sad
        SlimeEmotion.PATTED, SlimeEmotion.PLAYFUL -> SlimeVisualState.Patted
        else -> SlimeVisualState.Happy
    }
    
    var pattedAtMillis by remember { mutableStateOf(0L) }
    
    LaunchedEffect(pattedAtMillis) {
        if (pattedAtMillis > 0L) {
            kotlinx.coroutines.delay(900L)
            pattedAtMillis = 0L
        }
    }
    
    val visualState = if (pattedAtMillis > 0L) SlimeVisualState.Patted else baseVisualState
    
    val moodSpring = rememberMoodSpring(visualState)

    // ── Shape morphing state ──
    val morphState = remember { MorphState() }

    // ── Physics animatables ──
    val bodyOffset = remember { Animatable(Offset.Zero, Offset.VectorConverter) }
    val bodyScale = remember { Animatable(Offset(1f, 1f), Offset.VectorConverter) }
    val eyeLook = remember { Animatable(Offset.Zero, Offset.VectorConverter) }
    val rippleRadius = remember { Animatable(0f) }
    val rippleAlpha = remember { Animatable(0f) }
    var rippleCenter by remember { mutableStateOf(Offset.Zero) }

    // ── Breathing (infinite) ──
    val infiniteTransition = rememberInfiniteTransition(label = "breathe")
    val breatheScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = when (visualState) {
            SlimeVisualState.Angry -> 1.05f
            SlimeVisualState.Sleeping -> 1.015f
            else -> 1.035f
        },
        animationSpec = infiniteRepeatable(
            tween(
                durationMillis = when (visualState) {
                    SlimeVisualState.Angry -> 700
                    SlimeVisualState.Sleeping -> 3500
                    else -> 2200
                },
                easing = EaseInOutSine
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breathe"
    )

    // ── Sleeping float (for Zzz) ──
    val sleepFloat by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = -12f,
        animationSpec = infiniteRepeatable(tween(1800, easing = EaseInOutSine), RepeatMode.Reverse),
        label = "sleepFloat"
    )

    // ── Particles ──
    val particles = remember { mutableStateListOf<HeartParticle>() }
    var lastParticleTime by remember { mutableLongStateOf(0L) }

    // ── Active gesture tracking ──
    val activePointers = remember { mutableStateMapOf<PointerId, PointerTrack>() }
    var pinchStartSpan by remember { mutableFloatStateOf(0f) }

    // ── Trigger shape morph when emotion changes ──
    LaunchedEffect(visualState) {
        val target = when (visualState) {
            SlimeVisualState.Happy -> HappyShape
            SlimeVisualState.Sleeping -> SleepingShape
            SlimeVisualState.Angry -> AngryShape
            SlimeVisualState.Patted -> PattedShape
            SlimeVisualState.Sad -> SadShape
        }
        if (target !== morphState.toSpec) {
            // Capture the visual intermediate state as the new starting point
            morphState.fromSpec = lerpShape(
                morphState.fromSpec,
                morphState.toSpec,
                morphState.progress.value
            )
            morphState.toSpec = target
            morphState.progress.snapTo(0f)
            morphState.progress.animateTo(
                targetValue = 1f,
                animationSpec = tween(800, easing = EaseInOutCubic)
            )
        }
    }

    Box(modifier = modifier) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(Unit) {
                    awaitPointerEventScope {
                        while (true) {
                            val event = awaitPointerEvent()
                            val now = System.currentTimeMillis()

                            // ── Presses ──
                            event.changes.forEach { change ->
                                if (change.pressed && !change.previousPressed) {
                                    activePointers[change.id] = PointerTrack(
                                        downPos = change.position,
                                        current = change.position,
                                        prev = change.position,
                                        downTime = now
                                    )
                                    if (activePointers.size == 2) {
                                        val pts = activePointers.values.toList()
                                        pinchStartSpan =
                                            (pts[0].current - pts[1].current).getDistance()
                                    }
                                }
                            }

                            // ── Moves ──
                            event.changes.forEach { change ->
                                activePointers[change.id]?.let { track ->
                                    track.prev = track.current
                                    track.current = change.position
                                    track.addHistory(now, change.position)
                                }
                            }

                            // ── Releases ──
                            event.changes.forEach { change ->
                                if (!change.pressed && change.previousPressed) {
                                    val track = activePointers.remove(change.id)

                                    // End pinch → snap back
                                    if (activePointers.size < 2) {
                                        scope.launch {
                                            bodyScale.animateTo(
                                                Offset(1f, 1f),
                                                moodSpring
                                            )
                                        }
                                    }

                                    if (track != null) {
                                        val t = track
                                        val duration = now - t.downTime
                                        val dist = (t.current - t.downPos).getDistance()

                                        // ── POKE (quick tap) ──
                                        if (duration < 220 && dist < 18f) {
                                            pattedAtMillis = now
                                            rippleCenter = t.current
                                            scope.launch {
                                                rippleRadius.snapTo(0f)
                                                rippleAlpha.snapTo(0.55f)
                                                launch {
                                                    rippleRadius.animateTo(
                                                        80f,
                                                        tween(500, easing = EaseOutQuart)
                                                    )
                                                }
                                                launch {
                                                    rippleAlpha.animateTo(0f, tween(500))
                                                }
                                                // Wobble
                                                bodyScale.animateTo(
                                                    Offset(1.12f, 0.88f),
                                                    spring(
                                                        dampingRatio = 0.5f,
                                                        stiffness = Spring.StiffnessHigh
                                                    )
                                                )
                                                bodyScale.animateTo(
                                                    Offset(1f, 1f),
                                                    spring(
                                                        dampingRatio = 0.3f,
                                                        stiffness = Spring.StiffnessLow
                                                    )
                                                )
                                            }
                                        }
                                        // ── FLING (high-velocity swipe) ──
                                        else if (t.velocity > 1200f) {
                                            pattedAtMillis = now
                                            scope.launch {
                                                // Stretch on launch
                                                bodyScale.animateTo(
                                                    Offset(0.75f, 1.35f),
                                                    spring(
                                                        dampingRatio = 0.6f,
                                                        stiffness = Spring.StiffnessHigh
                                                    )
                                                )
                                                // Fly up
                                                bodyOffset.animateTo(
                                                    Offset(0f, -160f),
                                                    spring(
                                                        dampingRatio = 0.5f,
                                                        stiffness = Spring.StiffnessMedium
                                                    )
                                                )
                                                // Gravity slam down
                                                bodyOffset.animateTo(
                                                    Offset.Zero,
                                                    spring(
                                                        dampingRatio = 0.35f,
                                                        stiffness = Spring.StiffnessLow
                                                    )
                                                )
                                                // Floor squash
                                                bodyScale.animateTo(
                                                    Offset(1.25f, 0.75f),
                                                    spring(
                                                        dampingRatio = 0.55f,
                                                        stiffness = Spring.StiffnessHigh
                                                    )
                                                )
                                                bodyScale.animateTo(
                                                    Offset(1f, 1f),
                                                    spring(
                                                        dampingRatio = 0.3f,
                                                        stiffness = Spring.StiffnessLow
                                                    )
                                                )
                                            }
                                        }
                                    }
                                }
                            }

                            // ── Active pinch / squish ──
                            if (activePointers.size >= 2) {
                                pattedAtMillis = now
                                val pts = activePointers.values.take(2).toList()
                                val span = (pts[0].current - pts[1].current).getDistance()
                                val ratio = (span / pinchStartSpan).coerceIn(0.4f, 2.5f)
                                scope.launch {
                                    bodyScale.snapTo(Offset(ratio, 1f / ratio))
                                }
                            }

                            // ── Active drag → eye tracking + petting particles ──
                            if (activePointers.size == 1) {
                                val ptr = activePointers.values.first()

                                // Eye tracking target (artboard space)
                                val fracX =
                                    (ptr.current.x - size.width / 2f) / (size.width / 2f)
                                val fracY =
                                    (ptr.current.y - size.height / 2f) / (size.height / 2f)
                                val eyeTarget = Offset(
                                    (fracX * 10f).coerceIn(-10f, 10f),
                                    (fracY * 6f).coerceIn(-6f, 6f)
                                )
                                scope.launch {
                                    eyeLook.animateTo(eyeTarget, moodSpring)
                                }

                                // Petting hearts
                                if (ptr.velocity > 400f && now - lastParticleTime > 90 && particles.size < 25) {
                                    pattedAtMillis = now
                                    lastParticleTime = now
                                    val px = ptr.current.x + (Math.random().toFloat() - 0.5f) * 50f
                                    val py = ptr.current.y - 30f
                                    val drift = (Math.random().toFloat() - 0.5f) * 40f
                                    val alphaAnim = Animatable(1f)
                                    val yAnim = Animatable(0f)
                                    val p = HeartParticle(px, py, drift, alphaAnim, yAnim)
                                    particles.add(p)
                                    scope.launch {
                                        yAnim.animateTo(
                                            -120f,
                                            tween(1200, easing = EaseOutCubic)
                                        )
                                        alphaAnim.animateTo(0f, tween(1200))
                                        particles.remove(p)
                                    }
                                }
                            } else if (activePointers.isEmpty()) {
                                // Eyes drift back to center
                                scope.launch {
                                    eyeLook.animateTo(Offset.Zero, moodSpring)
                                }
                            }
                        }
                    }
                }
        ) {
            val artboardScale = size.minDimension / 200f
            val slimeCenter = Offset(size.width / 2f, size.height / 2f)

            // ── Compute interpolated body path ──
            val currentSpec = lerpShape(
                morphState.fromSpec,
                morphState.toSpec,
                morphState.progress.value
            )
            val bodyPath = buildPath(currentSpec)

            // ── Ripple (drawn in screen space, on top) ──
            if (rippleAlpha.value > 0.001f) {
                drawCircle(
                    color = Color.White.copy(alpha = rippleAlpha.value),
                    radius = rippleRadius.value,
                    center = rippleCenter,
                    style = Stroke(width = 3.5f)
                )
                drawCircle(
                    color = Color.White.copy(alpha = rippleAlpha.value * 0.25f),
                    radius = rippleRadius.value * 0.65f
                )
            }

            // ── Particles (screen space) ──
            particles.forEach { p ->
                val progress = 1f - (p.offsetY.value / -120f).coerceIn(0f, 1f)
                val x = p.x + p.drift * progress
                val y = p.y + p.offsetY.value
                drawHeart(x, y, p.alpha.value, 10f)
            }

            // ── Main slime transform block ──
            translate(left = bodyOffset.value.x, top = bodyOffset.value.y) {
                translate(
                    left = slimeCenter.x - 100f * artboardScale,
                    top = slimeCenter.y - 100f * artboardScale
                ) {
                    scale(artboardScale, artboardScale, pivot = Offset.Zero) {
                        scale(
                            scaleX = bodyScale.value.x,
                            scaleY = bodyScale.value.y,
                            pivot = Offset(100f, 190f)
                        ) {
                            scale(
                                scaleX = breatheScale,
                                scaleY = breatheScale,
                                pivot = Offset(100f, 190f)
                            ) {
                                
                                // ── RECORDING GLOW ──
                                if (isRecording) {
                                    drawCircle(
                                        brush = Brush.radialGradient(
                                            colors = listOf(Color(0xFF81D4FA).copy(alpha = 0.4f), Color.Transparent),
                                            center = Offset(100f, 100f),
                                            radius = 160f
                                        ),
                                        radius = 160f,
                                        center = Offset(100f, 100f)
                                    )
                                }

                                // ── Drop shadow ──
                                drawOval(
                                    color = Color.Black.copy(alpha = 0.12f),
                                    topLeft = Offset(30f, 188f),
                                    size = Size(140f, 14f)
                                )

                                // ── Gel body (radial gradient) ──
                                drawPath(
                                    path = bodyPath,
                                    brush = Brush.radialGradient(
                                        colors = listOf(
                                            Color(0xFFE0F7FA).copy(alpha = if(isRecording) 1.0f else 0.92f),
                                            Color(0xFF81D4FA),
                                            Color(0xFF29B6F6),
                                            Color(0xFF0277BD)
                                        ),
                                        center = Offset(88f, 98f),
                                        radius = 110f
                                    )
                                )

                                // ── Specular highlight ──
                                val highlight = PathParser().parsePathString(
                                    "M 35,48 C 60,32 98,32 128,48 C 112,40 75,40 35,48 Z"
                                ).toPath()
                                drawPath(
                                    path = highlight,
                                    brush = Brush.linearGradient(
                                        colors = listOf(
                                            Color.White.copy(alpha = 0.80f),
                                            Color.White.copy(alpha = 0.25f),
                                            Color.Transparent
                                        ),
                                        start = Offset(48f, 38f),
                                        end = Offset(122f, 72f)
                                    )
                                )

                                // ── Face (with eye tracking translation) ──
                                translate(left = eyeLook.value.x, top = eyeLook.value.y) {
                                    if (emotion == SlimeEmotion.SPEAKING) {
                                        drawSpeakingFace()
                                    } else {
                                        when (visualState) {
                                            SlimeVisualState.Happy -> drawHappyFace()
                                            SlimeVisualState.Sleeping -> drawSleepingFace(sleepFloat)
                                            SlimeVisualState.Angry -> drawAngryFace()
                                            SlimeVisualState.Patted -> drawPattedFace()
                                            SlimeVisualState.Sad -> drawSadFace()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// 4.  FACE RENDERERS
// ═══════════════════════════════════════════════════════════════════

private fun DrawScope.drawSpeakingFace() {
    val leftEye = PathParser().parsePathString("M 55,108 Q 75,92 95,108").toPath()
    val rightEye = PathParser().parsePathString("M 115,108 Q 135,92 155,108").toPath()

    drawPath(
        path = leftEye,
        color = Color(0xFF01579B),
        style = Stroke(width = 4.5f, cap = StrokeCap.Round)
    )
    drawPath(
        path = rightEye,
        color = Color(0xFF01579B),
        style = Stroke(width = 4.5f, cap = StrokeCap.Round)
    )

    // Open mouth
    drawCircle(
        color = Color(0xFF01579B),
        radius = 5f,
        center = Offset(105f, 125f)
    )

    drawCircle(
        color = Color(0xFFFF80AB).copy(alpha = 0.38f),
        radius = 13f,
        center = Offset(50f, 138f)
    )
    drawCircle(
        color = Color(0xFFFF80AB).copy(alpha = 0.38f),
        radius = 13f,
        center = Offset(150f, 138f)
    )
}

private fun DrawScope.drawHappyFace() {
    val left = PathParser().parsePathString("M 55,118 Q 75,92 95,118").toPath()
    val right = PathParser().parsePathString("M 115,118 Q 135,92 155,118").toPath()
    val stroke = Stroke(width = 4.5f, cap = StrokeCap.Round)

    drawPath(left, Color(0xFF01579B), style = stroke)
    drawPath(right, Color(0xFF01579B), style = stroke)

    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.38f), 13f, Offset(50f, 148f))
    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.38f), 13f, Offset(150f, 148f))
}

private fun DrawScope.drawSleepingFace(floatOffset: Float) {
    val left = PathParser().parsePathString("M 55,108 Q 75,132 95,108").toPath()
    val right = PathParser().parsePathString("M 115,108 Q 135,132 155,108").toPath()
    val stroke = Stroke(width = 4f, cap = StrokeCap.Round)

    drawPath(left, Color(0xFF01579B), style = stroke)
    drawPath(right, Color(0xFF01579B), style = stroke)

    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.28f), 11f, Offset(48f, 138f))
    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.28f), 11f, Offset(152f, 138f))

    // Bubble
    drawCircle(Color.White.copy(alpha = 0.65f), 9f, Offset(168f, 72f + floatOffset))
    drawCircle(Color.White.copy(alpha = 0.9f), 2.5f, Offset(165f, 69f + floatOffset))

    // Zzz
    val z1 = PathParser().parsePathString("M 170,58 L 178,58 L 170,65 L 178,65").toPath()
    val z2 = PathParser().parsePathString("M 180,42 L 192,42 L 180,54 L 192,54").toPath()

    translate(left = 0f, top = floatOffset) {
        drawPath(z1, Color(0xFF01579B).copy(alpha = 0.6f), style = Stroke(2f, cap = StrokeCap.Round))
    }
    translate(left = 0f, top = floatOffset * 1.3f) {
        drawPath(z2, Color(0xFF01579B).copy(alpha = 0.75f), style = Stroke(2.5f, cap = StrokeCap.Round))
    }
}

private fun DrawScope.drawAngryFace() {
    val left = PathParser().parsePathString("M 62,98 L 97,123").toPath()
    val right = PathParser().parsePathString("M 103,123 L 138,98").toPath()
    val stroke = Stroke(width = 5.5f, cap = StrokeCap.Round)

    drawPath(left, Color(0xFF01579B), style = stroke)
    drawPath(right, Color(0xFF01579B), style = stroke)

    // Popping vein
    val vein = PathParser().parsePathString("M 148,32 L 168,52 M 168,32 L 148,52").toPath()
    drawPath(vein, Color(0xFFD32F2F), style = Stroke(3.5f, cap = StrokeCap.Round))

    val accent = PathParser().parsePathString("M 140,28 Q 155,22 172,28").toPath()
    drawPath(accent, Color(0xFFD32F2F), style = Stroke(2f, cap = StrokeCap.Round))
}

private fun DrawScope.drawPattedFace() {
    // > <
    drawLine(Color(0xFF01579B), Offset(58f, 108f), Offset(72f, 118f), 4.5f, StrokeCap.Round)
    drawLine(Color(0xFF01579B), Offset(58f, 128f), Offset(72f, 118f), 4.5f, StrokeCap.Round)

    drawLine(Color(0xFF01579B), Offset(142f, 108f), Offset(128f, 118f), 4.5f, StrokeCap.Round)
    drawLine(Color(0xFF01579B), Offset(142f, 128f), Offset(128f, 118f), 4.5f, StrokeCap.Round)

    // Bright blushes
    drawCircle(Color(0xFFFF4081).copy(alpha = 0.55f), 14f, Offset(48f, 145f))
    drawCircle(Color(0xFFFF4081).copy(alpha = 0.55f), 14f, Offset(152f, 145f))
}

private fun DrawScope.drawSadFace() {
    val left = PathParser().parsePathString("M 60,115 Q 75,125 90,115").toPath()
    val right = PathParser().parsePathString("M 110,115 Q 125,125 140,115").toPath()
    drawPath(left, Color(0xFF01579B), style = Stroke(4f, cap = StrokeCap.Round))
    drawPath(right, Color(0xFF01579B), style = Stroke(4f, cap = StrokeCap.Round))

    val mouth = PathParser().parsePathString("M 85,150 Q 100,140 115,150").toPath()
    drawPath(mouth, Color(0xFF01579B), style = Stroke(3f, cap = StrokeCap.Round))

    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.22f), 11f, Offset(50f, 140f))
    drawCircle(Color(0xFFFF80AB).copy(alpha = 0.22f), 11f, Offset(150f, 140f))
}

// ═══════════════════════════════════════════════════════════════════
// 5.  PARTICLE DRAWING
// ═══════════════════════════════════════════════════════════════════

private fun DrawScope.drawHeart(x: Float, y: Float, alpha: Float, size: Float) {
    val s = size
    val path = Path().apply {
        moveTo(x, y + s / 4)
        cubicTo(x, y, x - s / 2, y, x - s / 2, y + s / 4)
        cubicTo(x - s / 2, y + s / 2, x, y + s * 0.75f, x, y + s)
        cubicTo(x, y + s * 0.75f, x + s / 2, y + s / 2, x + s / 2, y + s / 4)
        cubicTo(x + s / 2, y, x, y, x, y + s / 4)
        close()
    }
    drawPath(path, color = Color(0xFFFF4081).copy(alpha = alpha))
}
