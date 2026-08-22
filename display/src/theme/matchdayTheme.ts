import type { FootballResult, MatchPhase } from "../types/state";
import type { SceneTheme } from "./SceneTheme";

function opponentHue(identity: string): number {
  let hash = 2166136261;
  for (const character of identity) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return 190 + (Math.abs(hash) % 46);
}

export function getMatchdayTheme(opponentIdentity: string, phase: MatchPhase, isNight: boolean, result: FootballResult = "unknown"): SceneTheme {
  const hue = opponentHue(opponentIdentity);
  const live = phase === "live";
  const settled = phase === "half_time" || phase === "post_match" || phase === "finished";
  const finalWin = settled && result === "win";
  const finalLoss = settled && result === "loss";
  return {
    background: finalLoss ? "#0E0B0D" : isNight ? "#10070A" : "#17080C",
    ambient: `radial-gradient(circle at 18% 18%, rgba(202, 28, 58, ${finalWin ? ".3" : finalLoss ? ".08" : live ? ".24" : ".16"}), transparent 34%), radial-gradient(circle at 82% 74%, hsl(${hue} 42% 42% / ${finalLoss ? ".05" : ".11"}), transparent 36%)`,
    surface: "#211015",
    surfaceAlt: "#2B141B",
    panel: "rgba(28, 12, 17, .84)",
    line: "rgba(245, 229, 233, .18)",
    muted: "#B8A6AA",
    quiet: "#74656A",
    text: "#F2ECEE",
    accent: "#D51F3D",
    accentSoft: "rgba(213, 31, 61, .15)",
    success: "#5EAD7D",
    warning: "#D49A47",
    danger: "#E24F57",
    info: `hsl(${hue} 43% 62%)`,
    grid: "rgba(235, 216, 222, .025)",
    particles: {
      colors: ["#D51F3D", "#F0E8EB", "#8E2034", "#6F7888", "#B48F98"],
      density: finalWin ? 0.76 : finalLoss ? 0.34 : settled ? 0.52 : live ? 0.88 : 0.68,
      shape: "confetti",
      speed: finalWin ? 0.62 : finalLoss ? 0.34 : settled ? 0.48 : live ? 0.82 : 0.64,
    },
  };
}
