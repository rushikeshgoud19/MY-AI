import React, { useEffect, useRef } from 'react';

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

export const SlimeAvatar: React.FC<SlimeAvatarProps> = ({ state, size = 250 }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // Use Refs for state that changes rapidly to avoid destroying the canvas loop!
  const lastActiveRef = useRef<number>(Date.now());
  const blinkRef = useRef<boolean>(false);
  const mousePosRef = useRef({ x: 0, y: 0 }); // Normalized -1 to 1
  const stateRef = useRef<SlimeState>(state);

  // Sync state prop to ref
  useEffect(() => {
    stateRef.current = state;
    if (state.isThinking || state.isListening || state.isTalking) {
      lastActiveRef.current = Date.now();
    }
  }, [state]);

  // Track global mouse position without re-rendering React
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // Normalize to -1 (left/top) to 1 (right/bottom)
      const nx = (e.clientX / window.innerWidth) * 2 - 1;
      const ny = (e.clientY / window.innerHeight) * 2 - 1;
      mousePosRef.current = { x: nx, y: ny };
      lastActiveRef.current = Date.now(); // Keep awake when moving mouse
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Auto-blink
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      blinkRef.current = true;
      setTimeout(() => { blinkRef.current = false; }, 150);
    }, 3000 + Math.random() * 2000);
    return () => clearInterval(blinkInterval);
  }, []);

  // Render slime on canvas (Continuous loop, decoupled from React state!)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const centerX = size / 2;

    let animationFrameId: number;

    const render = () => {
      ctx.clearRect(0, 0, size, size);

      const time = Date.now() / 1000;
      const currentState = stateRef.current;
      const isSleeping = (Date.now() - lastActiveRef.current) > 120000; // 2 minutes
      const blink = blinkRef.current;

      // Core colors
      let baseColor = { r: 155, g: 212, b: 245 }; // Light blue
      if (currentState.valence < -0.3) {
        baseColor = { r: 130, g: 150, b: 200 }; // Sad purple-ish
      } else if (currentState.valence > 0.6 && currentState.arousal > 0.6) {
        baseColor = { r: 100, g: 255, b: 255 }; // Hyper cyan
      }
      if (currentState.isListening) {
        baseColor = { r: 255, g: 182, b: 193 }; // Cute pink when listening!
      }

      // Physics calculations
      const breathe = Math.sin(time * 2.5) * 2;

      // Happy bounce physics
      let bounceY = 0;
      let squishY = 1.0;
      let squishX = 1.0;

      if (currentState.valence > 0.5 || currentState.isListening) {
        // Jumping up and down
        bounceY = -Math.abs(Math.sin(time * 4)) * (size * 0.1);

        // Squish when hitting the ground
        if (Math.abs(bounceY) < 2) {
          squishY = 0.85;
          squishX = 1.15;
        } else if (Math.abs(bounceY) > size * 0.08) {
          squishY = 1.1;
          squishX = 0.9;
        }
      }

      ctx.save();
      
      // Push the slime further down the canvas to prevent the top from clipping
      ctx.translate(centerX, size * 0.70 + bounceY); 
      
      // Add a cute tilt when listening
      if (currentState.isListening) {
        ctx.rotate(Math.sin(time * 6) * 0.15);
      }
      
      ctx.scale(squishX, squishY);

      // Slime radius
      const r = (size * 0.35) + breathe;

      // 1. Draw Outer Slime Body
      ctx.beginPath();
      ctx.ellipse(0, -r, r * 1.2, r * 0.95, 0, 0, Math.PI * 2);

      const bodyGrad = ctx.createLinearGradient(0, -r * 2, 0, 0);
      bodyGrad.addColorStop(0, `rgba(255, 255, 255, 0.6)`);
      bodyGrad.addColorStop(0.2, `rgba(${baseColor.r}, ${baseColor.g}, ${baseColor.b}, 0.9)`);
      bodyGrad.addColorStop(0.8, `rgba(${baseColor.r - 20}, ${baseColor.g - 20}, ${baseColor.b - 20}, 0.95)`);
      bodyGrad.addColorStop(1, `rgba(${baseColor.r - 40}, ${baseColor.g - 40}, ${baseColor.b - 40}, 1)`);

      // Drop shadow for the whole slime
      ctx.shadowColor = `rgba(${baseColor.r}, ${baseColor.g}, ${baseColor.b}, 0.6)`;
      ctx.shadowBlur = 20;
      ctx.shadowOffsetY = 10;

      ctx.fillStyle = bodyGrad;
      ctx.fill();

      // Turn off shadow for inner elements
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;

      // 2. Inner Darker Core
      ctx.beginPath();
      // Organic blob shape for the core
      const coreR = r * 0.6;
      ctx.moveTo(-coreR * 0.8, -r * 0.6);
      ctx.quadraticCurveTo(0, -r * 1.3, coreR * 0.8, -r * 0.6);
      ctx.quadraticCurveTo(coreR * 1.2, -r * 0.2, coreR * 0.5, -r * 0.1);
      ctx.quadraticCurveTo(0, 0, -coreR * 0.5, -r * 0.1);
      ctx.quadraticCurveTo(-coreR * 1.2, -r * 0.2, -coreR * 0.8, -r * 0.6);

      ctx.fillStyle = `rgba(${baseColor.r - 60}, ${baseColor.g - 60}, ${baseColor.b - 50}, 0.6)`;
      ctx.fill();

      // 3. Highlight (Top Left)
      ctx.beginPath();
      ctx.ellipse(-r * 0.4, -r * 1.5, r * 0.35, r * 0.15, -Math.PI / 6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.fill();

      // 4. Blush Marks (Pink Ovals on Cheeks)
      let blushOpacity = currentState.valence > 0 ? 0.6 + (currentState.valence * 0.4) : 0.2;
      if (currentState.isListening) blushOpacity = 0.9;
      
      const blushY = -r * 0.7;
      const blushX = r * 0.7;

      ctx.beginPath();
      ctx.ellipse(-blushX, blushY, r * 0.25, r * 0.12, -0.1, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 150, 200, ${blushOpacity})`;
      ctx.fill();

      ctx.beginPath();
      ctx.ellipse(blushX, blushY, r * 0.25, r * 0.12, 0.1, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 150, 200, ${blushOpacity})`;
      ctx.fill();

      // 5. Eyes
      const eyeY = -r * 0.85;
      const eyeX = r * 0.35;
      const eyeW = r * 0.25;

      if (currentState.isListening) {
        // Cute ^ ^ eyes for listening
        ctx.strokeStyle = '#1e3a8a';
        ctx.lineWidth = Math.max(2, r * 0.08);
        ctx.lineCap = 'round';
        
        const eyeH = r * 0.15;
        // Left eye ^
        ctx.beginPath();
        ctx.moveTo(-eyeX - eyeW, eyeY + eyeH/2);
        ctx.quadraticCurveTo(-eyeX - eyeW/2, eyeY - eyeH, -eyeX, eyeY + eyeH/2);
        ctx.stroke();

        // Right eye ^
        ctx.beginPath();
        ctx.moveTo(eyeX, eyeY + eyeH/2);
        ctx.quadraticCurveTo(eyeX + eyeW/2, eyeY - eyeH, eyeX + eyeW, eyeY + eyeH/2);
        ctx.stroke();

        // Floating Sparkles / Music Notes
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const symbols = ['🎵', '✨', '🎶'];
        for(let i=0; i<3; i++) {
            const floatY = (time * 2 + i * 2) % (Math.PI * 2);
            const nx = Math.sin(time * 3 + i * 2.5) * r * 1.8;
            const ny = -r * 1.8 - floatY * r * 0.4;
            ctx.font = `${r*0.4}px Arial`;
            ctx.fillText(symbols[i], nx, ny);
        }

      } else if (isSleeping) {
        // Closed slits: \ /
        const eyeH = currentState.valence > 0.5 ? r * 0.1 : r * 0.05;

        ctx.strokeStyle = '#1e3a8a';
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';

        // Left eye
        ctx.beginPath();
        ctx.moveTo(-eyeX - eyeW, eyeY);
        ctx.quadraticCurveTo(-eyeX - (eyeW/2), eyeY + eyeH, -eyeX, eyeY + (eyeH * 0.5));
        ctx.stroke();

        // Right eye
        ctx.beginPath();
        ctx.moveTo(eyeX, eyeY + (eyeH * 0.5));
        ctx.quadraticCurveTo(eyeX + (eyeW/2), eyeY + eyeH, eyeX + eyeW, eyeY);
        ctx.stroke();
      } else {
        // Awake: Open Eyes
        const eyeH = blink ? r * 0.02 : r * 0.15; // Blink mechanic

        // Calculate offset based on mouse position
        const maxEyeOffset = r * 0.1;
        const maxPupilOffset = r * 0.08;
        const mPos = mousePosRef.current;
        const eOffsetX = mPos.x * maxEyeOffset;
        const eOffsetY = mPos.y * maxEyeOffset;
        const pOffsetX = mPos.x * maxPupilOffset;
        const pOffsetY = mPos.y * maxPupilOffset;

        // Left eye
        ctx.beginPath();
        ctx.ellipse(-eyeX - (eyeW/2) + eOffsetX, eyeY + eOffsetY, eyeW * 0.4, eyeH, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#1e3a8a';
        ctx.fill();

        // Right eye
        ctx.beginPath();
        ctx.ellipse(eyeX + (eyeW/2) + eOffsetX, eyeY + eOffsetY, eyeW * 0.4, eyeH, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#1e3a8a';
        ctx.fill();

        if (!blink) {
          // Pupils
          ctx.beginPath();
          ctx.arc(-eyeX - (eyeW/2) + eOffsetX + pOffsetX, eyeY + eOffsetY + pOffsetY, eyeW * 0.15, 0, Math.PI * 2);
          ctx.fillStyle = '#fff';
          ctx.fill();

          ctx.beginPath();
          ctx.arc(eyeX + (eyeW/2) + eOffsetX + pOffsetX, eyeY + eOffsetY + pOffsetY, eyeW * 0.15, 0, Math.PI * 2);
          ctx.fillStyle = '#fff';
          ctx.fill();
        }
      }

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };

  // Only recreate the loop if the canvas size changes! 
  // We removed state and lastActive to prevent the lag!
  }, [size]);

  const handleSlimeClick = () => {
    // Manually wake up and act happy when clicked
    lastActiveRef.current = Date.now();
    blinkRef.current = true;
    setTimeout(() => { blinkRef.current = false; }, 200);
  };

  return (
    <div
      className="classic-blob-container"
      style={{ width: size, height: size, cursor: 'pointer', transition: 'transform 0.2s ease-out' }}
      onClick={handleSlimeClick}
      onMouseOver={(e) => (e.currentTarget.style.transform = 'scale(1.05)')}
      onMouseOut={(e) => (e.currentTarget.style.transform = 'scale(1)')}
    >
      <canvas
        ref={canvasRef}
        className="blob-canvas"
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};
