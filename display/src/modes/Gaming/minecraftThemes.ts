import type { SceneTheme } from "../../theme/SceneTheme";

const shared = {
  success: "#55B982",
  warning: "#D9A24D",
  danger: "#DE6767",
};

const dimensions: Record<string, SceneTheme> = {
  overworld: {
    ...shared,
    background: "#E8E1CA",
    ambient: "linear-gradient(180deg, rgba(99, 173, 214, .22), transparent 48%), radial-gradient(circle at 14% 84%, rgba(89, 129, 68, .2), transparent 36%)",
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
    particles: { colors: ["#568248", "#8E6B45", "#62A5C8", "#B69B5D", "#7A9B63"], density: .95, shape: "square", speed: .78 },
  },
  nether: {
    ...shared,
    background: "#160C0B",
    ambient: "radial-gradient(circle at 80% 22%, rgba(219, 79, 33, .24), transparent 34%), radial-gradient(circle at 12% 84%, rgba(121, 24, 29, .3), transparent 40%)",
    surface: "#241210",
    surfaceAlt: "#351915",
    panel: "rgba(32, 15, 13, .8)",
    line: "rgba(238, 128, 69, .2)",
    muted: "#C6A096",
    quiet: "#896B65",
    text: "#FFF3EA",
    accent: "#E05B32",
    accentSoft: "rgba(224, 91, 50, .17)",
    info: "#E9A14B",
    grid: "rgba(224, 91, 50, .055)",
    particles: { colors: ["#E05B32", "#A52B2F", "#E9A14B", "#6F2627", "#F1C071"], density: .82, shape: "square", speed: .62 },
  },
  end: {
    ...shared,
    background: "#0E0C14",
    ambient: "radial-gradient(circle at 74% 20%, rgba(112, 74, 142, .25), transparent 34%), radial-gradient(circle at 16% 82%, rgba(219, 218, 161, .12), transparent 40%)",
    surface: "#181421",
    surfaceAlt: "#24202D",
    panel: "rgba(20, 16, 29, .82)",
    line: "rgba(218, 213, 169, .17)",
    muted: "#B9B1C3",
    quiet: "#787082",
    text: "#F4F1DF",
    accent: "#D8D49F",
    accentSoft: "rgba(216, 212, 159, .14)",
    info: "#9B76B3",
    grid: "rgba(216, 212, 159, .04)",
    particles: { colors: ["#D8D49F", "#77598D", "#A783BA", "#ECE7BC", "#45344F"], density: .68, shape: "mixed", speed: .48 },
  },
};

function canonicalDimension(value: string): string {
  const path = value.toLowerCase().split(":").at(-1) ?? value.toLowerCase();
  if (path === "the_nether") return "nether";
  if (path === "the_end") return "end";
  return path;
}

function hash(value: string): number {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

export function formatMinecraftIdentifier(value: string): string {
  const path = value.split(":").at(-1) ?? value;
  return path.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getMinecraftDimensionTheme(dimension: string): SceneTheme {
  const normalized = canonicalDimension(dimension);
  const known = dimensions[normalized];
  if (known) return known;

  const seed = hash(dimension) % 360;
  const accent = `hsl(${seed} 45% 54%)`;
  const companion = `hsl(${(seed + 62) % 360} 38% 62%)`;
  return {
    ...dimensions.end,
    ambient: `radial-gradient(circle at 76% 20%, hsl(${seed} 48% 45% / .2), transparent 36%), radial-gradient(circle at 15% 82%, hsl(${(seed + 62) % 360} 45% 48% / .13), transparent 40%)`,
    accent,
    accentSoft: `hsl(${seed} 45% 54% / .15)`,
    info: companion,
    particles: { colors: [accent, companion, "#D9D5C7", "#7D7885"], density: .72, shape: "mixed", speed: .56 },
  };
}
