"use client";
import * as React from "react";
import type { HexaPhase } from "@/lib/hexa/speech";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  ox: number;
  oy: number;
  angle: number;
  radius: number;
  size: number;
  hue: number;
  phaseOff: number;
  orbitSpeed: number;
};

function createParticles(count: number, cx: number, cy: number): Particle[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2;
    const x = cx + Math.cos(Math.random() * Math.PI * 2) * (30 + Math.random() * 140);
    const y = cy + Math.sin(Math.random() * Math.PI * 2) * (30 + Math.random() * 140);
    // Dense ring: most particles on the main circle, a few on inner/outer edge
    const lane = i % 8;
    const baseR = lane < 6 ? 86 + (lane % 3) * 2.2 : lane === 6 ? 78 : 96;
    return {
      x,
      y,
      vx: (Math.random() - 0.5) * 1.8,
      vy: (Math.random() - 0.5) * 1.8,
      ox: x,
      oy: y,
      angle: angle + Math.random() * 0.04,
      radius: baseR + Math.random() * 1.4,
      size: 0.9 + Math.random() * 1.8,
      hue: 195 + Math.random() * 100,
      phaseOff: Math.random() * Math.PI * 2,
      orbitSpeed: 0.012 + Math.random() * 0.02,
    };
  });
}

export function HexaOrb({
  phase,
  energy,
}: {
  phase: HexaPhase;
  energy: number;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const particlesRef = React.useRef<Particle[]>([]);
  const rafRef = React.useRef<number>(0);
  const phaseRef = React.useRef(phase);
  const energyRef = React.useRef(energy);
  const tRef = React.useRef(0);

  React.useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);
  React.useEffect(() => {
    energyRef.current = energy;
  }, [energy]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cssSize = 300;
    canvas.width = cssSize * dpr;
    canvas.height = cssSize * dpr;
    canvas.style.width = `${cssSize}px`;
    canvas.style.height = `${cssSize}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cx = cssSize / 2;
    const cy = cssSize / 2;
    particlesRef.current = createParticles(420, cx, cy);

    const draw = () => {
      const p = phaseRef.current;
      const e = energyRef.current;
      tRef.current += 1;
      const t = tRef.current;
      const speaking = p === "speaking";
      const listening = p === "listening";
      const thinking = p === "thinking";
      const assemble = speaking ? 1 : thinking ? 0.9 : listening ? 0.5 : 0.2;
      const gather = speaking ? 0.99 : thinking ? 0.88 : listening ? 0.48 : 0.18;

      ctx.clearRect(0, 0, cssSize, cssSize);

      const aura = ctx.createRadialGradient(cx, cy, 20, cx, cy, 140 + e * 28);
      aura.addColorStop(0, `rgba(120, 160, 255, ${0.1 + e * 0.18})`);
      aura.addColorStop(0.45, `rgba(150, 90, 255, ${0.07 + e * 0.1})`);
      aura.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = aura;
      ctx.beginPath();
      ctx.arc(cx, cy, 150 + e * 18, 0, Math.PI * 2);
      ctx.fill();

      if (gather > 0.25) {
        ctx.beginPath();
        ctx.arc(cx, cy + (speaking ? Math.sin(t / 10) * 2 : 0), 88 + e * 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(170, 200, 255, ${0.1 + gather * 0.22})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      const particles = particlesRef.current;
      for (const part of particles) {
        part.angle += part.orbitSpeed * (speaking ? 2 + e * 0.8 : listening ? 1.25 : 0.75);

        // Keep ring tight so particles clearly form a circle
        const ringR =
          part.radius +
          (speaking ? Math.sin(t / 9 + part.phaseOff) * (1.2 + e * 2.5) : Math.sin(t / 20 + part.phaseOff) * 0.8);
        const wobbleY = speaking ? Math.sin(t / 10 + part.phaseOff) * (1.5 + e * 4) : 0;
        const targetX = cx + Math.cos(part.angle) * ringR;
        const targetY = cy + Math.sin(part.angle) * ringR + wobbleY;

        part.ox += part.vx * 0.4;
        part.oy += part.vy * 0.4;
        if (Math.hypot(part.ox - cx, part.oy - cy) > 140) {
          part.vx *= -1;
          part.vy *= -1;
        }
        part.vx += (Math.random() - 0.5) * 0.06;
        part.vy += (Math.random() - 0.5) * 0.06;
        part.vx *= 0.985;
        part.vy *= 0.985;

        const freeX = part.ox + Math.cos(t / 18 + part.phaseOff) * 12;
        const freeY = part.oy + Math.sin(t / 15 + part.phaseOff) * 12;

        const nx = freeX * (1 - gather) + targetX * gather;
        const ny = freeY * (1 - gather) + targetY * gather;

        part.x += (nx - part.x) * (0.12 + assemble * 0.28);
        part.y += (ny - part.y) * (0.12 + assemble * 0.28);

        const flicker = 0.55 + Math.sin(t / 4 + part.phaseOff) * 0.25 + (speaking ? e * 0.25 : 0);
        const size = part.size * (speaking ? 1 + e * 0.45 : 1) * (0.85 + flicker * 0.3);

        const grad = ctx.createRadialGradient(part.x, part.y, 0, part.x, part.y, size * 2.8);
        grad.addColorStop(0, `hsla(${part.hue}, 95%, 75%, ${Math.min(1, flicker)})`);
        grad.addColorStop(0.45, `hsla(${part.hue + 40}, 90%, 60%, ${0.32 * flicker})`);
        grad.addColorStop(1, "hsla(260, 80%, 50%, 0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(part.x, part.y, size * 2.8, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(255,255,255,${0.55 + flicker * 0.4})`;
        ctx.beginPath();
        ctx.arc(part.x, part.y, size * 0.4, 0, Math.PI * 2);
        ctx.fill();
      }

      if (gather > 0.55) {
        const eyeY = cy + (speaking ? Math.sin(t / 9) * 2 : 0);
        const eyeGlow = 0.5 + Math.sin(t / 6) * 0.2 + e * 0.3;
        for (const ex of [cx - 18, cx + 18]) {
          const eg = ctx.createRadialGradient(ex, eyeY, 0, ex, eyeY, 10);
          eg.addColorStop(0, `rgba(255,255,255,${eyeGlow})`);
          eg.addColorStop(1, "rgba(255,255,255,0)");
          ctx.fillStyle = eg;
          ctx.beginPath();
          ctx.arc(ex, eyeY, 10, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = "#fff";
          ctx.beginPath();
          ctx.arc(ex, eyeY, 2.4 + e * 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div className="relative flex size-60 items-center justify-center sm:size-72" aria-hidden="true">
      <canvas ref={canvasRef} className="hexa-particle-canvas size-[300px] max-w-full" />
    </div>
  );
}
