import React, { useEffect, useRef, useState } from 'react';

export interface SlimeState {
  valence: number;      // -1 to 1 (sad to happy)
  arousal: number;      // 0 to 1 (calm to excited)
  trust: number;        // 0 to 1
  isThinking: boolean;
  isListening: boolean;
  isTalking: boolean;
}

interface SlimeAvatarProps {
  state: SlimeState;
  size?: number;
}

export const SlimeAvatar: React.FC<SlimeAvatarProps> = ({ state, size = 200 }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [blink, setBlink] = useState(false);
  
  // Auto-blink every 3-5 seconds
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 150);
    }, 3000 + Math.random() * 2000);
    return () => clearInterval(blinkInterval);
  }, []);

  // Render slime on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const dpr = window.devicePixelRatio || 1;
    
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);
    
    const centerX = size / 2;
    const centerY = size / 2;
    
    // Color based on emotion
    const baseColor = getSlimeColor(state.valence, state.arousal);
    const glowColor = getGlowColor(state.valence);
    
    let animationFrameId: number;

    const render = () => {
      // Clear
      ctx.clearRect(0, 0, size, size);
      
      // Glow effect (CSS-like box-shadow)
      const gradient = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, size * 0.6
      );
      gradient.addColorStop(0, glowColor + '40');  // 25% opacity
      gradient.addColorStop(1, glowColor + '00');  // 0% opacity
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, size, size);
      
      // Slime body — organic blob shape using bezier curves
      ctx.beginPath();
      const time = Date.now() / 1000;
      const breathe = Math.sin(time * 2) * 3;  // Breathing animation
      
      // Dynamic shape based on emotion
      const baseRadius = size * 0.35;
      const stretchX = state.arousal > 0.7 ? 1.15 : 1.0;  // Excited = stretched
      const stretchY = state.valence < -0.5 ? 0.85 : 1.0;   // Sad = squished
      
      // Draw organic blob
      const points = 8;
      for (let i = 0; i <= points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const wobble = Math.sin(angle * 3 + time * 3) * 4;
        const r = baseRadius + wobble + breathe;
        const x = centerX + Math.cos(angle) * r * stretchX;
        const y = centerY + Math.sin(angle) * r * stretchY;
        
        if (i === 0) ctx.moveTo(x, y);
        else {
          const prevAngle = ((i - 1) / points) * Math.PI * 2;
          const cpx = centerX + Math.cos(prevAngle + 0.4) * r * 1.2 * stretchX;
          const cpy = centerY + Math.sin(prevAngle + 0.4) * r * 1.2 * stretchY;
          ctx.quadraticCurveTo(cpx, cpy, x, y);
        }
      }
      ctx.closePath();
      
      // Fill with gradient
      const bodyGradient = ctx.createRadialGradient(
        centerX - size * 0.1, centerY - size * 0.1, 0,
        centerX, centerY, baseRadius
      );
      bodyGradient.addColorStop(0, lightenColor(baseColor, 30));
      bodyGradient.addColorStop(0.7, baseColor);
      bodyGradient.addColorStop(1, darkenColor(baseColor, 20));
      
      ctx.fillStyle = bodyGradient;
      ctx.fill();
      
      // Highlight (shiny slime look)
      ctx.beginPath();
      ctx.ellipse(
        centerX - size * 0.12,
        centerY - size * 0.15,
        size * 0.12,
        size * 0.08,
        -0.5, 0, Math.PI * 2
      );
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.fill();
      
      // Eyes
      drawEyes(ctx, centerX, centerY, size, state, blink);
      
      // Mouth
      drawMouth(ctx, centerX, centerY, size, state);
      
      // Thinking bubbles
      if (state.isThinking) {
        drawThinkingBubbles(ctx, centerX, centerY, size, time);
      }
      
      // Listening ripple
      if (state.isListening) {
        drawListeningRipple(ctx, centerX, centerY, size, time);
      }
      
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
    
  }, [state, blink, size]);
  
  return (
    <canvas
      ref={canvasRef}
      style={{
        width: size,
        height: size,
        filter: 'drop-shadow(0 0 20px rgba(139, 92, 246, 0.3))'
      }}
    />
  );
};

// ─── DRAWING HELPERS ───

function drawEyes(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, state: SlimeState, blink: boolean) {
  const eyeY = cy - size * 0.08;
  const eyeSpacing = size * 0.18;
  const eyeSize = size * 0.08;
  
  // Eye shape changes with emotion
  const eyeHeight = blink ? eyeSize * 0.1 : 
                    state.valence < -0.5 ? eyeSize * 0.6 :  // Sad = flat
                    eyeSize;
  
  // Left eye
  ctx.beginPath();
  ctx.ellipse(cx - eyeSpacing, eyeY, eyeSize, eyeHeight, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#1a1a2e';
  ctx.fill();
  
  // Right eye
  ctx.beginPath();
  ctx.ellipse(cx + eyeSpacing, eyeY, eyeSize, eyeHeight, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#1a1a2e';
  ctx.fill();
  
  if (!blink) {
    // Pupils — follow "attention" direction
    const pupilOffset = state.isListening ? size * 0.02 : 0;
    const pupilSize = eyeSize * 0.4;
    
    // Left pupil
    ctx.beginPath();
    ctx.arc(cx - eyeSpacing + pupilOffset, eyeY, pupilSize, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    
    // Eye shine
    ctx.beginPath();
    ctx.arc(cx - eyeSpacing - pupilSize * 0.3, eyeY - pupilSize * 0.3, pupilSize * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.fill();
    
    // Right pupil
    ctx.beginPath();
    ctx.arc(cx + eyeSpacing + pupilOffset, eyeY, pupilSize, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    
    // Eye shine
    ctx.beginPath();
    ctx.arc(cx + eyeSpacing - pupilSize * 0.3, eyeY - pupilSize * 0.3, pupilSize * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.fill();
  }
}

function drawMouth(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, state: SlimeState) {
  const mouthY = cy + size * 0.12;
  const mouthWidth = size * 0.2;
  
  ctx.beginPath();
  
  if (state.valence > 0.5) {
    // Happy smile
    ctx.arc(cx, mouthY - size * 0.03, mouthWidth * 0.5, 0.2, Math.PI - 0.2);
    ctx.lineWidth = size * 0.025;
    ctx.strokeStyle = '#1a1a2e';
    ctx.lineCap = 'round';
    ctx.stroke();
    
    // Blush
    ctx.beginPath();
    ctx.ellipse(cx - size * 0.22, mouthY - size * 0.05, size * 0.06, size * 0.04, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 100, 150, 0.2)';
    ctx.fill();
    
    ctx.beginPath();
    ctx.ellipse(cx + size * 0.22, mouthY - size * 0.05, size * 0.06, size * 0.04, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 100, 150, 0.2)';
    ctx.fill();
    
  } else if (state.valence < -0.5) {
    // Sad frown
    ctx.arc(cx, mouthY + size * 0.08, mouthWidth * 0.5, Math.PI + 0.2, -0.2);
    ctx.lineWidth = size * 0.025;
    ctx.strokeStyle = '#1a1a2e';
    ctx.lineCap = 'round';
    ctx.stroke();
    
  } else if (state.arousal > 0.7) {
    // Surprised O
    ctx.beginPath();
    ctx.ellipse(cx, mouthY, size * 0.05, size * 0.07, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#1a1a2e';
    ctx.fill();
    
  } else {
    // Neutral small smile
    ctx.arc(cx, mouthY, mouthWidth * 0.4, 0.1, Math.PI - 0.1);
    ctx.lineWidth = size * 0.02;
    ctx.strokeStyle = '#1a1a2e';
    ctx.lineCap = 'round';
    ctx.stroke();
  }
}

function drawThinkingBubbles(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, time: number) {
  const bubbles = [
    { x: cx + size * 0.45, y: cy - size * 0.35, r: size * 0.04, delay: 0 },
    { x: cx + size * 0.55, y: cy - size * 0.45, r: size * 0.06, delay: 0.3 },
    { x: cx + size * 0.65, y: cy - size * 0.55, r: size * 0.08, delay: 0.6 },
  ];
  
  bubbles.forEach(b => {
    const opacity = (Math.sin(time * 2 + b.delay) + 1) / 2 * 0.6;
    ctx.beginPath();
    ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
    ctx.fill();
  });
}

function drawListeningRipple(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, time: number) {
  const rippleRadius = (time * 50) % (size * 0.6);
  const opacity = 1 - (rippleRadius / (size * 0.6));
  
  ctx.beginPath();
  ctx.arc(cx, cy, rippleRadius, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(139, 92, 246, ${opacity * 0.3})`;
  ctx.lineWidth = 2;
  ctx.stroke();
}

// ─── COLOR HELPERS ───

function getSlimeColor(valence: number, arousal: number): string {
  if (valence < -0.5) return '#6366f1';      // Indigo — sad
  if (valence < -0.2) return '#8b5cf6';      // Violet — meh
  if (valence < 0.3) return '#a855f7';       // Purple — neutral
  if (valence < 0.7) return '#d946ef';      // Fuchsia — happy
  return '#f472b6';                           // Pink — ecstatic
}

function getGlowColor(valence: number): string {
  if (valence < -0.5) return '#4338ca';      // Dark indigo
  if (valence < 0) return '#7c3aed';         // Dark violet
  if (valence < 0.5) return '#9333ea';       // Dark purple
  return '#db2777';                            // Dark pink
}

function lightenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.min(255, (num >> 16) + amt);
  const G = Math.min(255, ((num >> 8) & 0x00FF) + amt);
  const B = Math.min(255, (num & 0x0000FF) + amt);
  return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
}

function darkenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.max(0, (num >> 16) - amt);
  const G = Math.max(0, ((num >> 8) & 0x00FF) - amt);
  const B = Math.max(0, (num & 0x0000FF) - amt);
  return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
}
