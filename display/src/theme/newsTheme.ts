import type { NewsImportanceLevel, NewsTopic } from "../types/state";
import type { SceneTheme } from "./SceneTheme";
import { idleTheme } from "./themes";

const TOPIC_ACCENTS: Record<NewsTopic, string> = {
  world: "#355A82",
  germany: "#3E5F7C",
  local: "#4C6B62",
  politics: "#3F5878",
  economy: "#8A673D",
  technology: "#5B5FB0",
  science: "#50747C",
  weather: "#4D7792",
  transport: "#B0782F",
  sports: "#A34F57",
  entertainment: "#805E8D",
  other: "#5F6964",
};

export function getNewsTheme(topic: NewsTopic, level: NewsImportanceLevel): SceneTheme {
  const accent = TOPIC_ACCENTS[topic];
  const major = level === "major";
  return {
    ...idleTheme,
    background: major ? "#EDEEEB" : "#F3F2EE",
    ambient: major
      ? `radial-gradient(circle at 82% 16%, color-mix(in srgb, ${accent} 20%, transparent), transparent 38%), linear-gradient(120deg, rgba(23, 24, 22, .03), transparent 42%)`
      : `radial-gradient(circle at 78% 16%, color-mix(in srgb, ${accent} 12%, transparent), transparent 36%)`,
    surfaceAlt: major ? "#E2E4E0" : "#EAE9E3",
    panel: "rgba(255, 255, 255, .76)",
    line: `color-mix(in srgb, ${accent} 24%, #DAD8D1)`,
    accent,
    accentSoft: `color-mix(in srgb, ${accent} 11%, #FFFFFF)`,
    grid: `color-mix(in srgb, ${accent} 5%, transparent)`,
    particles: {
      colors: [accent, "#7D8782", "#A58A64", "#778497"],
      density: major ? 0.62 : 0.42,
      speed: major ? 0.52 : 0.38,
      shape: "mixed",
    },
  };
}
