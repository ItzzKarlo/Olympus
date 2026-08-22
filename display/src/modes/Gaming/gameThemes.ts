import type { ParticleTheme, SceneTheme } from "../../theme/SceneTheme";

export interface GamePresentation {
  label: string;
  motif: "blocks" | "chaos" | "energy" | "orbit";
  theme: SceneTheme;
}

interface GameColors {
  background: string;
  accent: string;
  accentSoft: string;
  ambient: string;
  grid: string;
  info: string;
  line: string;
  muted: string;
  panel: string;
  particles: ParticleTheme;
  quiet: string;
  surface: string;
  surfaceAlt: string;
  text: string;
}

const common = {
  success: "#55B982",
  warning: "#D9A24D",
  danger: "#DE7171",
};

function makeTheme(colors: GameColors): SceneTheme {
  return { ...colors, ...common };
}

const GAME_PRESENTATIONS: Record<string, GamePresentation> = {
  fortnite: {
    label: "High energy",
    motif: "energy",
    theme: makeTheme({
      background: "#11112B",
      ambient: "radial-gradient(circle at 78% 14%, rgba(79, 220, 255, .25), transparent 30%), radial-gradient(circle at 15% 80%, rgba(156, 74, 255, .28), transparent 36%)",
      surface: "#1A1940",
      surfaceAlt: "#252257",
      panel: "rgba(21, 20, 54, .76)",
      line: "rgba(173, 172, 255, .24)",
      muted: "#C0C0DF",
      quiet: "#8988B3",
      text: "#FAFAFF",
      accent: "#9D6BFF",
      accentSoft: "rgba(157, 107, 255, .18)",
      info: "#4FDCFF",
      grid: "rgba(112, 136, 255, .075)",
      particles: {
        colors: ["#9D6BFF", "#4FDCFF", "#637BFF", "#FF76CE", "#F6C85F"],
        density: 1.1,
        shape: "mixed",
        speed: 1.2,
      },
    }),
  },
  minecraft: {
    label: "Overworld",
    motif: "blocks",
    theme: makeTheme({
      background: "#E8E1CA",
      ambient: "linear-gradient(180deg, rgba(99, 173, 214, .2), transparent 46%), radial-gradient(circle at 14% 82%, rgba(89, 129, 68, .19), transparent 34%)",
      surface: "#F7F2E4",
      surfaceAlt: "#D9D1B6",
      panel: "rgba(247, 242, 228, .78)",
      line: "rgba(76, 91, 54, .24)",
      muted: "#56604A",
      quiet: "#818674",
      text: "#25291F",
      accent: "#568248",
      accentSoft: "rgba(86, 130, 72, .16)",
      info: "#4E8BAA",
      grid: "rgba(81, 103, 58, .07)",
      particles: {
        colors: ["#568248", "#8E6B45", "#62A5C8", "#B69B5D", "#7A9B63"],
        density: 0.95,
        shape: "square",
        speed: 0.78,
      },
    }),
  },
  "among-us": {
    label: "Deep space",
    motif: "orbit",
    theme: makeTheme({
      background: "#0D1020",
      ambient: "radial-gradient(circle at 82% 22%, rgba(202, 57, 70, .2), transparent 28%), radial-gradient(circle at 20% 76%, rgba(62, 92, 164, .18), transparent 34%)",
      surface: "#161A30",
      surfaceAlt: "#202640",
      panel: "rgba(16, 20, 40, .78)",
      line: "rgba(179, 190, 225, .18)",
      muted: "#ABB3CC",
      quiet: "#707A99",
      text: "#F4F6FC",
      accent: "#D94F58",
      accentSoft: "rgba(217, 79, 88, .18)",
      info: "#6BA8D5",
      grid: "rgba(146, 157, 197, .04)",
      particles: {
        colors: ["#D94F58", "#6BA8D5", "#E7E9F2", "#7B6FB5", "#E3BC61"],
        density: 0.7,
        shape: "mixed",
        speed: 0.65,
      },
    }),
  },
  "goat-simulator": {
    label: "Unsupervised",
    motif: "chaos",
    theme: makeTheme({
      background: "#FFF0D2",
      ambient: "radial-gradient(circle at 76% 18%, rgba(255, 83, 119, .23), transparent 34%), radial-gradient(circle at 18% 82%, rgba(255, 166, 48, .24), transparent 38%)",
      surface: "#FFF9EB",
      surfaceAlt: "#F3D9AE",
      panel: "rgba(255, 249, 235, .78)",
      line: "rgba(113, 63, 34, .22)",
      muted: "#725844",
      quiet: "#9E8068",
      text: "#362217",
      accent: "#EA4E77",
      accentSoft: "rgba(234, 78, 119, .16)",
      info: "#238F91",
      grid: "rgba(164, 92, 39, .06)",
      particles: {
        colors: ["#EA4E77", "#FF9F2E", "#20A5A5", "#845EC2", "#E3C13B"],
        density: 1.2,
        shape: "confetti",
        speed: 1.35,
      },
    }),
  },
};

GAME_PRESENTATIONS["goat-simulator-3"] = GAME_PRESENTATIONS["goat-simulator"];

function hash(value: string): number {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function hue(seed: number, offset = 0, alpha = 1): string {
  return `hsl(${(seed + offset) % 360} 66% 57% / ${alpha})`;
}

function hueToHex(seed: number, offset = 0): string {
  const h = ((seed + offset) % 360) / 60;
  const chroma = 0.72;
  const secondary = chroma * (1 - Math.abs((h % 2) - 1));
  const channels = [[chroma, secondary, 0], [secondary, chroma, 0], [0, chroma, secondary], [0, secondary, chroma], [secondary, 0, chroma], [chroma, 0, secondary]][Math.floor(h) % 6];
  return `#${channels.map((channel) => Math.round((channel + 0.14) * 255).toString(16).padStart(2, "0")).join("")}`;
}

function fallbackPresentation(key: string): GamePresentation {
  const seed = hash(key || "olympus-game") % 360;
  const primary = hueToHex(seed);
  const secondary = hueToHex(seed, 68);
  return {
    label: "Active game",
    motif: "energy",
    theme: makeTheme({
      background: "#12151B",
      ambient: `radial-gradient(circle at 78% 18%, ${hue(seed, 0, 0.18)}, transparent 34%), radial-gradient(circle at 18% 82%, ${hue(seed, 68, 0.14)}, transparent 38%)`,
      surface: "#1A1E26",
      surfaceAlt: "#232935",
      panel: "rgba(20, 24, 31, .78)",
      line: "rgba(217, 224, 235, .16)",
      muted: "#B7BDC7",
      quiet: "#7F8793",
      text: "#F7F8FA",
      accent: primary,
      accentSoft: `color-mix(in srgb, ${primary} 18%, transparent)`,
      info: secondary,
      grid: "rgba(205, 214, 229, .045)",
      particles: {
        colors: [primary, secondary, "#E6E9EF", hueToHex(seed, 132)],
        density: 0.95,
        shape: "mixed",
        speed: 1,
      },
    }),
  };
}

export function getGamePresentation(gameId: string, gameName: string): GamePresentation {
  return GAME_PRESENTATIONS[gameId] ?? fallbackPresentation(gameId || gameName);
}
