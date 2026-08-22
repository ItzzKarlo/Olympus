import type { SceneTheme } from "./SceneTheme";

interface Rgb {
  r: number;
  g: number;
  b: number;
}

interface Bucket {
  color: Rgb;
  count: number;
  score: number;
}

const clamp = (value: number, minimum = 0, maximum = 255) =>
  Math.min(maximum, Math.max(minimum, value));

function rgbToHex({ r, g, b }: Rgb): string {
  return `#${[r, g, b]
    .map((channel) => Math.round(clamp(channel)).toString(16).padStart(2, "0"))
    .join("")}`;
}

function mix(first: Rgb, second: Rgb, amount: number): Rgb {
  return {
    r: first.r * (1 - amount) + second.r * amount,
    g: first.g * (1 - amount) + second.g * amount,
    b: first.b * (1 - amount) + second.b * amount,
  };
}

function rgba(color: Rgb, alpha: number): string {
  return `rgba(${Math.round(color.r)}, ${Math.round(color.g)}, ${Math.round(color.b)}, ${alpha})`;
}

function luminance(color: Rgb): number {
  const linear = [color.r, color.g, color.b].map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function saturation(color: Rgb): number {
  const channels = [color.r, color.g, color.b];
  return (Math.max(...channels) - Math.min(...channels)) / 255;
}

function distance(first: Rgb, second: Rgb): number {
  return Math.hypot(first.r - second.r, first.g - second.g, first.b - second.b);
}

function hueToRgb(hue: number, saturationValue = 0.58, lightness = 0.52): Rgb {
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturationValue;
  const sector = (((hue % 360) + 360) % 360) / 60;
  const secondary = chroma * (1 - Math.abs((sector % 2) - 1));
  const values: [number, number, number][] = [
    [chroma, secondary, 0],
    [secondary, chroma, 0],
    [0, chroma, secondary],
    [0, secondary, chroma],
    [secondary, 0, chroma],
    [chroma, 0, secondary],
  ];
  const [red, green, blue] = values[Math.floor(sector) % 6];
  const match = lightness - chroma / 2;
  return { r: (red + match) * 255, g: (green + match) * 255, b: (blue + match) * 255 };
}

function hash(value: string): number {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function buildTheme(colors: Rgb[]): SceneTheme {
  const primary = colors[0];
  const secondary = colors[1] ?? hueToRgb(210);
  const third = colors[2] ?? mix(primary, secondary, 0.5);
  const isDark = luminance(primary) < 0.23 && luminance(secondary) < 0.34;
  const base = isDark
    ? mix(primary, { r: 13, g: 15, b: 17 }, 0.78)
    : mix(primary, { r: 245, g: 244, b: 240 }, 0.84);
  const accent = isDark
    ? mix(primary, { r: 255, g: 255, b: 255 }, 0.2)
    : mix(primary, { r: 20, g: 22, b: 21 }, luminance(primary) > 0.42 ? 0.3 : 0.08);
  const accentTwo = isDark
    ? mix(secondary, { r: 255, g: 255, b: 255 }, 0.16)
    : mix(secondary, { r: 20, g: 22, b: 21 }, luminance(secondary) > 0.45 ? 0.26 : 0.05);

  return {
    background: rgbToHex(base),
    ambient: `radial-gradient(circle at 18% 16%, ${rgba(primary, isDark ? 0.38 : 0.19)}, transparent 42%), radial-gradient(circle at 84% 78%, ${rgba(secondary, isDark ? 0.3 : 0.16)}, transparent 38%)`,
    surface: isDark ? "#17191B" : "#FFFFFF",
    surfaceAlt: isDark ? rgba({ r: 255, g: 255, b: 255 }, 0.08) : rgba(primary, 0.1),
    panel: isDark ? "rgba(22, 24, 26, 0.78)" : "rgba(255, 255, 255, 0.78)",
    line: isDark ? "rgba(255, 255, 255, 0.16)" : "rgba(23, 24, 22, 0.14)",
    muted: isDark ? "#B7BAB6" : "#5E625C",
    quiet: isDark ? "#858A85" : "#8D928A",
    text: isDark ? "#F7F7F3" : "#171816",
    accent: rgbToHex(accent),
    accentSoft: isDark ? rgba(accent, 0.17) : rgba(accent, 0.12),
    success: isDark ? "#6DB58E" : "#3F8F67",
    warning: isDark ? "#D6A458" : "#B97C2B",
    danger: isDark ? "#D47A7A" : "#B95151",
    info: rgbToHex(accentTwo),
    grid: isDark ? "rgba(255, 255, 255, 0.045)" : rgba(accent, 0.05),
    particles: {
      colors: [
        rgbToHex(accent),
        rgbToHex(accentTwo),
        rgbToHex(third),
        rgbToHex(mix(primary, secondary, 0.35)),
        rgbToHex(mix(secondary, third, 0.4)),
      ],
      density: 0.88,
      speed: 0.72,
    },
  };
}

export function fallbackMediaTheme(key: string): SceneTheme {
  const seed = hash(key || "olympus-media");
  const hue = seed % 360;
  const distance = 42 + ((seed >>> 8) % 56);
  return buildTheme([
    hueToRgb(hue, 0.58, 0.46),
    hueToRgb(hue + distance, 0.5, 0.5),
    hueToRgb(hue - 34, 0.46, 0.55),
  ]);
}

function sampleArtwork(url: string): Promise<Rgb[]> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.decoding = "async";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 36;
        canvas.height = 36;
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) throw new Error("Canvas is unavailable");
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        const buckets = new Map<string, Bucket>();
        for (let index = 0; index < pixels.length; index += 4) {
          if (pixels[index + 3] < 210) continue;
          const color = { r: pixels[index], g: pixels[index + 1], b: pixels[index + 2] };
          const light = luminance(color);
          if (light < 0.018 || light > 0.96) continue;
          const key = `${Math.round(color.r / 24)}:${Math.round(color.g / 24)}:${Math.round(color.b / 24)}`;
          const bucket = buckets.get(key);
          const score = 0.35 + saturation(color) * 0.9;
          if (bucket) {
            bucket.count += 1;
            bucket.score += score;
          } else {
            buckets.set(key, { color, count: 1, score });
          }
        }
        const selected: Rgb[] = [];
        for (const bucket of [...buckets.values()].sort((a, b) => b.score - a.score || b.count - a.count)) {
          if (selected.every((color) => distance(color, bucket.color) > 68)) {
            selected.push(bucket.color);
          }
          if (selected.length === 3) break;
        }
        if (selected.length < 2) throw new Error("Artwork palette was too narrow");
        resolve(selected);
      } catch (error) {
        reject(error);
      }
    };
    image.onerror = () => reject(new Error("Artwork could not be loaded"));
    image.src = url;
  });
}

export async function mediaThemeFromArtwork(
  artworkUrl: string | null,
  fallbackKey: string,
): Promise<SceneTheme> {
  if (!artworkUrl) return fallbackMediaTheme(fallbackKey);
  try {
    return buildTheme(await sampleArtwork(artworkUrl));
  } catch {
    return fallbackMediaTheme(fallbackKey);
  }
}
