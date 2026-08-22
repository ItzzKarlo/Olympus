import type { WeatherCondition } from "../types/state";
import type { SceneTheme } from "./SceneTheme";
import { idleTheme } from "./themes";


const WEATHER_OVERRIDES: Partial<Record<WeatherCondition, Partial<SceneTheme>>> = {
  clear: {
    ambient: "radial-gradient(circle at 76% 12%, rgba(224, 169, 73, .13), transparent 34%), radial-gradient(circle at 18% 82%, rgba(91, 111, 216, .07), transparent 32%)",
    particles: { colors: ["#5B6FD8", "#D6A446", "#3F8F67", "#C65C5C", "#4E89B8"], density: .95, speed: .92 },
  },
  mostly_clear: {
    ambient: "radial-gradient(circle at 76% 12%, rgba(205, 166, 92, .11), transparent 34%), radial-gradient(circle at 18% 82%, rgba(91, 111, 216, .07), transparent 32%)",
  },
  cloudy: {
    background: "#F1F1EE",
    ambient: "radial-gradient(circle at 75% 16%, rgba(114, 126, 139, .09), transparent 38%)",
    muted: "#626863",
    particles: { colors: ["#71839A", "#8B918A", "#5B6FD8", "#839C8A"], density: .76, speed: .68 },
  },
  fog: {
    background: "#F0F1EF",
    ambient: "linear-gradient(135deg, rgba(129, 141, 147, .08), transparent 56%)",
    particles: { colors: ["#829098", "#A0A7A3", "#70839C", "#8B938C"], density: .65, speed: .55 },
  },
  drizzle: {
    background: "#EFF2F3",
    ambient: "radial-gradient(circle at 76% 12%, rgba(69, 116, 151, .11), transparent 38%)",
    accent: "#5076A0",
    accentSoft: "#E2E9EF",
    particles: { colors: ["#5076A0", "#718CA5", "#5C8E89", "#8495A5"], density: .7, speed: .58 },
  },
  rain: {
    background: "#EDF1F3",
    ambient: "radial-gradient(circle at 76% 12%, rgba(60, 105, 142, .14), transparent 40%), linear-gradient(140deg, rgba(86, 111, 126, .05), transparent 55%)",
    accent: "#456D96",
    accentSoft: "#DEE8EF",
    particles: { colors: ["#456D96", "#6888A2", "#527D7B", "#7890A0"], density: .72, speed: .56 },
  },
  heavy_rain: {
    background: "#E9EEF0",
    ambient: "radial-gradient(circle at 74% 12%, rgba(52, 83, 110, .17), transparent 42%)",
    accent: "#3E6285",
    accentSoft: "#D9E3E9",
    particles: { colors: ["#3E6285", "#58768C", "#496D6E", "#758592"], density: .68, speed: .52 },
  },
  snow: {
    background: "#F5F7F6",
    ambient: "radial-gradient(circle at 76% 14%, rgba(121, 156, 180, .11), transparent 40%)",
    accent: "#6687A0",
    accentSoft: "#E6EDF1",
    particles: { colors: ["#AFC5D2", "#D1DADD", "#7795AA", "#9BB8B2"], density: .85, speed: .45 },
  },
  thunderstorm: {
    background: "#E8E9EC",
    ambient: "radial-gradient(circle at 76% 12%, rgba(79, 70, 119, .17), transparent 42%)",
    accent: "#5F5C91",
    accentSoft: "#DFDFEB",
    particles: { colors: ["#5F5C91", "#77799A", "#A18455", "#5C777F"], density: .68, speed: .64 },
  },
};

export function getIdleWeatherTheme(condition?: WeatherCondition): SceneTheme {
  const override = condition ? WEATHER_OVERRIDES[condition] : undefined;
  return override ? { ...idleTheme, ...override } : idleTheme;
}
