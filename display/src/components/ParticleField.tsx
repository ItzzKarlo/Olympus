import { useEffect, useRef } from "react";

import type { ParticleTheme } from "../theme/SceneTheme";

type ConfettiShape = "circle" | "dash" | "square" | "triangle";

interface Particle {
  collisionRadius: number;
  color: Rgb;
  colorIndex: number;
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

interface Rgb {
  r: number;
  g: number;
  b: number;
}

const DEFAULT_COLORS = ["#5B6FD8", "#3F8F67", "#C88A32", "#C65C5C", "#4E89B8"];
const SHAPES: ConfettiShape[] = ["dash", "square", "triangle", "circle"];
const MAX_SPEED = 0.24;

function parseColor(color: string): Rgb {
  const normalized = color.replace("#", "");
  if (/^[0-9a-f]{6}$/i.test(normalized)) {
    return {
      r: Number.parseInt(normalized.slice(0, 2), 16),
      g: Number.parseInt(normalized.slice(2, 4), 16),
      b: Number.parseInt(normalized.slice(4, 6), 16),
    };
  }
  return { r: 91, g: 111, b: 216 };
}

interface ParticleFieldProps {
  theme?: ParticleTheme;
}

function shapesFor(family: ParticleTheme["shape"]): ConfettiShape[] {
  if (family === "square") return ["square"];
  if (family === "confetti") return ["dash", "square", "triangle"];
  return SHAPES;
}

export function ParticleField({ theme }: ParticleFieldProps) {
  const colors = theme?.colors ?? DEFAULT_COLORS;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const paletteRef = useRef<Rgb[]>(colors.map(parseColor));
  const themeRef = useRef(theme);
  paletteRef.current = (colors.length > 0 ? colors : DEFAULT_COLORS).map(parseColor);
  themeRef.current = theme;

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d", { alpha: true });
    if (!canvas || !context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let particles: Particle[] = [];
    let frame = 0;
    let width = 0;
    let height = 0;

    const createParticles = () => {
      const mobile = width < 720;
      const density = Math.min(1.35, Math.max(0.2, themeRef.current?.density ?? 1));
      const count = Math.min(
        mobile ? 44 : 96,
        Math.round(((width * height) / (mobile ? 17_000 : 19_000)) * density),
      );

      const nextParticles: Particle[] = [];
      const particleCount = Math.max(
        count,
        Math.round((mobile ? 28 : 54) * density),
      );

      for (let index = 0; index < particleCount; index += 1) {
        const shapes = shapesFor(themeRef.current?.shape);
        const shape = shapes[index % shapes.length];
        const particleWidth = 3 + Math.random() * 5;
        const particleHeight =
          shape === "dash" ? particleWidth * 2.4 : particleWidth;
        const collisionRadius = Math.max(particleWidth, particleHeight) / 2 + 4;
        let x = collisionRadius + Math.random() * (width - collisionRadius * 2);
        let y = collisionRadius + Math.random() * (height - collisionRadius * 2);

        for (let attempt = 0; attempt < 20; attempt += 1) {
          const clear = nextParticles.every((particle) => {
            const dx = particle.x - x;
            const dy = particle.y - y;
            const minimumDistance = particle.collisionRadius + collisionRadius;
            return dx * dx + dy * dy >= minimumDistance * minimumDistance;
          });
          if (clear) break;
          x = collisionRadius + Math.random() * (width - collisionRadius * 2);
          y = collisionRadius + Math.random() * (height - collisionRadius * 2);
        }

        const direction = Math.random() * Math.PI * 2;
        const speedScale = Math.min(1.55, Math.max(0.3, themeRef.current?.speed ?? 1));
        const speed = (0.07 + Math.random() * 0.11) * speedScale;
        const colorIndex = index % paletteRef.current.length;
        nextParticles.push({
          collisionRadius,
          color: { ...paletteRef.current[colorIndex] },
          colorIndex,
          height: particleHeight,
          phase: Math.random() * Math.PI * 2,
          rotation: Math.random() * Math.PI,
          rotationSpeed: (Math.random() - 0.5) * 0.004,
          shape,
          vx: Math.cos(direction) * speed,
          vy: Math.sin(direction) * speed,
          width: particleWidth,
          x,
          y,
        });
      }

      particles = nextParticles;
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
      const target = paletteRef.current[particle.colorIndex % paletteRef.current.length];
      particle.color.r += (target.r - particle.color.r) * 0.025;
      particle.color.g += (target.g - particle.color.g) * 0.025;
      particle.color.b += (target.b - particle.color.b) * 0.025;
      context.save();
      context.translate(particle.x, particle.y);
      context.rotate(particle.rotation);
      context.fillStyle = `rgb(${Math.round(particle.color.r)}, ${Math.round(particle.color.g)}, ${Math.round(particle.color.b)})`;
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

    const keepParticlesApart = () => {
      for (let firstIndex = 0; firstIndex < particles.length; firstIndex += 1) {
        const first = particles[firstIndex];

        for (
          let secondIndex = firstIndex + 1;
          secondIndex < particles.length;
          secondIndex += 1
        ) {
          const second = particles[secondIndex];
          let dx = second.x - first.x;
          let dy = second.y - first.y;
          let distanceSquared = dx * dx + dy * dy;
          const minimumDistance = first.collisionRadius + second.collisionRadius;

          if (distanceSquared >= minimumDistance * minimumDistance) continue;
          if (distanceSquared < 0.01) {
            dx = Math.cos(first.phase);
            dy = Math.sin(first.phase);
            distanceSquared = 1;
          }

          const distance = Math.sqrt(distanceSquared);
          const normalX = dx / distance;
          const normalY = dy / distance;
          const correction = (minimumDistance - distance) * 0.5;
          first.x -= normalX * correction;
          first.y -= normalY * correction;
          second.x += normalX * correction;
          second.y += normalY * correction;

          const relativeVelocity =
            (second.vx - first.vx) * normalX +
            (second.vy - first.vy) * normalY;
          if (relativeVelocity < 0) {
            const impulse = relativeVelocity * 0.42;
            first.vx += normalX * impulse;
            first.vy += normalY * impulse;
            second.vx -= normalX * impulse;
            second.vy -= normalY * impulse;
          }
        }
      }
    };

    const draw = (time = 0) => {
      context.clearRect(0, 0, width, height);

      for (const particle of particles) {
        if (!reducedMotion.matches) {
          particle.vx += Math.cos(time * 0.00008 + particle.phase) * 0.00055;
          particle.vy += Math.sin(time * 0.00007 + particle.phase) * 0.00055;
          particle.vx *= 0.9995;
          particle.vy *= 0.9995;

          const speed = Math.hypot(particle.vx, particle.vy);
          const maximumSpeed = MAX_SPEED * Math.min(1.55, Math.max(0.3, themeRef.current?.speed ?? 1));
          if (speed > maximumSpeed) {
            particle.vx = (particle.vx / speed) * maximumSpeed;
            particle.vy = (particle.vy / speed) * maximumSpeed;
          }

          particle.x += particle.vx;
          particle.y += particle.vy;
          particle.rotation += particle.rotationSpeed;

          if (particle.x <= particle.collisionRadius) {
            particle.x = particle.collisionRadius;
            particle.vx = Math.abs(particle.vx);
          } else if (particle.x >= width - particle.collisionRadius) {
            particle.x = width - particle.collisionRadius;
            particle.vx = -Math.abs(particle.vx);
          }

          if (particle.y <= particle.collisionRadius) {
            particle.y = particle.collisionRadius;
            particle.vy = Math.abs(particle.vy);
          } else if (particle.y >= height - particle.collisionRadius) {
            particle.y = height - particle.collisionRadius;
            particle.vy = -Math.abs(particle.vy);
          }
        }
      }

      if (!reducedMotion.matches) keepParticlesApart();
      for (const particle of particles) drawParticle(particle);

      context.globalAlpha = 1;
      if (!reducedMotion.matches && !document.hidden) {
        frame = window.requestAnimationFrame(draw);
      }
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
    document.addEventListener("visibilitychange", onVisibilityChange);
    reducedMotion.addEventListener("change", onMotionChange);

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      reducedMotion.removeEventListener("change", onMotionChange);
    };
  }, []);

  return <canvas ref={canvasRef} className="particle-field" aria-hidden="true" />;
}
