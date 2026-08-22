import type { SceneTheme } from "./SceneTheme";

export const idleTheme: SceneTheme = {
  background: "#F5F4F0",
  ambient:
    "radial-gradient(circle at 78% 14%, rgba(91, 111, 216, 0.08), transparent 32%)",
  surface: "#FFFFFF",
  surfaceAlt: "#ECEAE4",
  panel: "rgba(255, 255, 255, 0.88)",
  line: "#DAD8D1",
  muted: "#666A63",
  quiet: "#979B93",
  text: "#171816",
  accent: "#5B6FD8",
  accentSoft: "#E8EBFA",
  success: "#3F8F67",
  warning: "#C88A32",
  danger: "#C65C5C",
  info: "#4E89B8",
  grid: "rgba(91, 111, 216, 0.045)",
  particles: {
    colors: ["#5B6FD8", "#3F8F67", "#C88A32", "#C65C5C", "#4E89B8"],
  },
};

export const developmentTheme: SceneTheme = {
  ...idleTheme,
  background: "#F1F3F5",
  ambient:
    "radial-gradient(circle at 82% 12%, rgba(63, 111, 151, 0.12), transparent 32%), radial-gradient(circle at 18% 80%, rgba(92, 91, 176, 0.08), transparent 30%)",
  surfaceAlt: "#E5E9ED",
  panel: "rgba(250, 252, 253, 0.89)",
  line: "#D3D9DE",
  muted: "#59636B",
  quiet: "#8B959D",
  accent: "#4C67A8",
  accentSoft: "#E2E8F4",
  info: "#3F7F9D",
  grid: "rgba(63, 91, 125, 0.05)",
  particles: {
    colors: ["#4C67A8", "#3F7F9D", "#6B5CA5", "#7895AA", "#3F8F82"],
    density: 0.9,
    speed: 0.82,
  },
};
