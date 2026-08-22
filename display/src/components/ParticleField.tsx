import { useEffect, useRef } from "react";

type ConfettiShape = "circle" | "dash" | "square" | "triangle";

interface Particle {
  anchorX: number;
  anchorY: number;
  color: string;
  height: number;
  phase: number;
  rotation: number;
  rotationSpeed: number;
  shape: ConfettiShape;
  vx: number;
  vy: number;
  width: number;
  x: number;
  y: number;
}

const COLORS = ["#5B6FD8", "#3F8F67", "#C88A32", "#C65C5C", "#4E89B8"];
const SHAPES: ConfettiShape[] = ["dash", "square", "triangle", "circle"];

export function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d", { alpha: true });
    if (!canvas || !context) return;

    const pointer = { active: false, x: -10_000, y: -10_000 };
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let particles: Particle[] = [];
    let frame = 0;
    let width = 0;
    let height = 0;

    const createParticles = () => {
      const mobile = width < 720;
      const count = Math.min(
        mobile ? 44 : 96,
        Math.round((width * height) / (mobile ? 17_000 : 19_000)),
      );

      particles = Array.from(
        { length: Math.max(count, mobile ? 28 : 54) },
        (_, index) => {
          const anchorX = Math.random() * width;
          const anchorY = Math.random() * height;
          const shape = SHAPES[index % SHAPES.length];
          const particleWidth = 3 + Math.random() * 5;

          return {
            anchorX,
            anchorY,
            color: COLORS[index % COLORS.length],
            height: shape === "dash" ? particleWidth * 2.4 : particleWidth,
            phase: Math.random() * Math.PI * 2,
            rotation: Math.random() * Math.PI,
            rotationSpeed: (Math.random() - 0.5) * 0.004,
            shape,
            vx: 0,
            vy: 0,
            width: particleWidth,
            x: anchorX,
            y: anchorY,
          };
        },
      );
    };

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      createParticles();
    };

    const drawParticle = (particle: Particle) => {
      context.save();
      context.translate(particle.x, particle.y);
      context.rotate(particle.rotation);
      context.fillStyle = particle.color;
      context.globalAlpha = particle.shape === "circle" ? 0.38 : 0.5;

      if (particle.shape === "circle") {
        context.beginPath();
        context.arc(0, 0, particle.width / 2, 0, Math.PI * 2);
        context.fill();
      } else if (particle.shape === "triangle") {
        context.beginPath();
        context.moveTo(0, -particle.height / 2);
        context.lineTo(particle.width / 2, particle.height / 2);
        context.lineTo(-particle.width / 2, particle.height / 2);
        context.closePath();
        context.fill();
      } else {
        context.fillRect(
          -particle.width / 2,
          -particle.height / 2,
          particle.width,
          particle.height,
        );
      }

      context.restore();
    };

    const draw = (time = 0) => {
      context.clearRect(0, 0, width, height);

      for (const particle of particles) {
        if (!reducedMotion.matches) {
          const driftX = Math.sin(time * 0.00014 + particle.phase) * 11;
          const driftY = Math.cos(time * 0.00011 + particle.phase) * 13;
          particle.vx += (particle.anchorX + driftX - particle.x) * 0.0028;
          particle.vy += (particle.anchorY + driftY - particle.y) * 0.0028;

          if (pointer.active) {
            const dx = particle.x - pointer.x;
            const dy = particle.y - pointer.y;
            const distanceSquared = dx * dx + dy * dy;
            const influenceRadius = width < 720 ? 100 : 155;

            if (
              distanceSquared < influenceRadius * influenceRadius &&
              distanceSquared > 0.1
            ) {
              const distance = Math.sqrt(distanceSquared);
              const force = (1 - distance / influenceRadius) * 0.75;
              particle.vx += (dx / distance) * force;
              particle.vy += (dy / distance) * force;
            }
          }

          particle.vx *= 0.94;
          particle.vy *= 0.94;
          particle.x += particle.vx;
          particle.y += particle.vy;
          particle.rotation += particle.rotationSpeed;
        }

        drawParticle(particle);
      }

      context.globalAlpha = 1;
      if (!reducedMotion.matches && !document.hidden) {
        frame = window.requestAnimationFrame(draw);
      }
    };

    const onPointerMove = (event: PointerEvent) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
    };
    const onPointerLeave = () => {
      pointer.active = false;
    };
    const onVisibilityChange = () => {
      window.cancelAnimationFrame(frame);
      if (!document.hidden && !reducedMotion.matches) {
        frame = window.requestAnimationFrame(draw);
      }
    };
    const onMotionChange = () => {
      window.cancelAnimationFrame(frame);
      draw();
    };

    resize();
    draw();
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerleave", onPointerLeave);
    document.addEventListener("visibilitychange", onVisibilityChange);
    reducedMotion.addEventListener("change", onMotionChange);

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerleave", onPointerLeave);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      reducedMotion.removeEventListener("change", onMotionChange);
    };
  }, []);

  return <canvas ref={canvasRef} className="particle-field" aria-hidden="true" />;
}
