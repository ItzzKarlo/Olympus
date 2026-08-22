import type { WeatherCondition } from "../types/state";
import type { SceneTheme } from "./SceneTheme";
import { getIdleWeatherTheme } from "./idleWeatherTheme";

const NIGHT_FALLBACK_PARTICLES = ["#59647A", "#586C68", "#75664F", "#725757", "#526A7A"];

function hexChannels(value: string): [number, number, number] | null {
  const match = /^#([0-9a-f]{6})$/i.exec(value);
  if (!match) return null;
  return [
    Number.parseInt(match[1].slice(0, 2), 16),
    Number.parseInt(match[1].slice(2, 4), 16),
    Number.parseInt(match[1].slice(4, 6), 16),
  ];
}

function mutedParticle(color: string, index: number): string {
  const source = hexChannels(color) ?? hexChannels(NIGHT_FALLBACK_PARTICLES[index % NIGHT_FALLBACK_PARTICLES.length]);
  if (!source) return NIGHT_FALLBACK_PARTICLES[index % NIGHT_FALLBACK_PARTICLES.length];
  const target: [number, number, number] = [61, 69, 84];
  const mixed = source.map((channel, channelIndex) =>
    Math.round(channel * 0.48 + target[channelIndex] * 0.52),
  );
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

export function applyNightAdaptation(theme: SceneTheme, resting = false): SceneTheme {
  return {
    ...theme,
    background: "#090C12",
    ambient: `linear-gradient(rgba(5, 7, 11, .64), rgba(5, 7, 11, .82)), ${theme.ambient}`,
    surface: `color-mix(in srgb, ${theme.surface} 12%, #111722)`,
    surfaceAlt: `color-mix(in srgb, ${theme.surfaceAlt} 12%, #171D27)`,
    panel: "rgba(17, 22, 31, .82)",
    line: `color-mix(in srgb, ${theme.line} 24%, rgba(128, 140, 158, .18))`,
    muted: "#939AA4",
    quiet: "#646B75",
    text: "#E5E7E9",
    accent: `color-mix(in srgb, ${theme.accent} 64%, #8993AF)`,
    accentSoft: `color-mix(in srgb, ${theme.accent} 13%, rgba(110, 122, 151, .08))`,
    grid: "rgba(137, 149, 174, .025)",
    particles: {
      ...theme.particles,
      colors: theme.particles.colors.map(mutedParticle),
      density: resting ? 0.32 : 0.44,
      speed: resting ? 0.34 : 0.42,
    },
  };
}

export function getNightTheme(condition?: WeatherCondition): SceneTheme {
  return applyNightAdaptation(getIdleWeatherTheme(condition), true);
}
