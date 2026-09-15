import type { SceneTheme } from "./SceneTheme";

export type Season = "spring" | "summer" | "autumn" | "winter";

export type SeasonalEvent =
  | "new-year"
  | "valentine"
  | "easter"
  | "may-day"
  | "midsummer"
  | "unity-day"
  | "halloween"
  | "st-martin"
  | "advent"
  | "st-nicholas"
  | "christmas-eve"
  | "christmas"
  | "new-years-eve";

interface SeasonalPalette {
  accent: string;
  accentSoft: string;
  ambient: string;
  background: string;
  grid: string;
  line: string;
  muted: string;
  particles: string[];
  quiet: string;
  surface: string;
  surfaceAlt: string;
}

export interface SeasonalPresentation {
  event: SeasonalEvent | null;
  glyphs: string[];
  icon: string;
  id: string;
  label: string;
  palette: SeasonalPalette;
  season: Season;
}

const DAY_MS = 86_400_000;

const SEASONAL: Record<Season, Omit<SeasonalPresentation, "event" | "id" | "season">> = {
  spring: {
    label: "Spring",
    icon: "✿",
    glyphs: ["✿", "❀", "·", "✦"],
    palette: {
      background: "#F3F6EF",
      surface: "#FBFCF8",
      surfaceAlt: "#E7EDE0",
      line: "#D2DDC9",
      muted: "#66705F",
      quiet: "#929C8A",
      accent: "#6F925E",
      accentSoft: "#E4EEDD",
      grid: "rgba(111, 146, 94, 0.05)",
      ambient:
        "radial-gradient(circle at 82% 12%, rgba(232, 158, 187, .15), transparent 30%), radial-gradient(circle at 16% 78%, rgba(111, 146, 94, .10), transparent 32%)",
      particles: ["#6F925E", "#E29AB7", "#F2C7D8", "#9DBA8E", "#E8B75C"],
    },
  },
  summer: {
    label: "Summer",
    icon: "☀",
    glyphs: ["✦", "☀", "·", "✧"],
    palette: {
      background: "#F8F3E7",
      surface: "#FFFDF7",
      surfaceAlt: "#F0E8D5",
      line: "#E0D4B9",
      muted: "#756B56",
      quiet: "#A49A83",
      accent: "#D28B35",
      accentSoft: "#F7E8C9",
      grid: "rgba(210, 139, 53, 0.045)",
      ambient:
        "radial-gradient(circle at 84% 8%, rgba(244, 184, 74, .18), transparent 30%), radial-gradient(circle at 12% 82%, rgba(74, 164, 174, .10), transparent 32%)",
      particles: ["#E5A33E", "#F1C45C", "#54A7AF", "#7CBF9B", "#ED8F63"],
    },
  },
  autumn: {
    label: "Autumn",
    icon: "🍂",
    glyphs: ["🍂", "🍁", "◆", "·"],
    palette: {
      background: "#F4EEE4",
      surface: "#FCF8F1",
      surfaceAlt: "#EAE0D2",
      line: "#DCCBB6",
      muted: "#746556",
      quiet: "#9F9182",
      accent: "#B96932",
      accentSoft: "#F0DDC9",
      grid: "rgba(185, 105, 50, 0.05)",
      ambient:
        "radial-gradient(circle at 82% 12%, rgba(185, 105, 50, .16), transparent 31%), radial-gradient(circle at 12% 82%, rgba(124, 93, 48, .09), transparent 34%)",
      particles: ["#B96932", "#D3974D", "#8A5B35", "#C55435", "#D7B46A"],
    },
  },
  winter: {
    label: "Winter",
    icon: "❄",
    glyphs: ["❄", "✦", "·", "✧"],
    palette: {
      background: "#EEF3F7",
      surface: "#FAFCFD",
      surfaceAlt: "#E2EAF0",
      line: "#CAD7E0",
      muted: "#5E6D78",
      quiet: "#8D9BA5",
      accent: "#5D83A7",
      accentSoft: "#DDEAF4",
      grid: "rgba(93, 131, 167, 0.05)",
      ambient:
        "radial-gradient(circle at 82% 10%, rgba(117, 158, 193, .16), transparent 31%), radial-gradient(circle at 14% 84%, rgba(171, 198, 219, .12), transparent 34%)",
      particles: ["#FFFFFF", "#BFD5E6", "#7FA7C7", "#D8E6F0", "#87A5BD"],
    },
  },
};

const EVENTS: Record<SeasonalEvent, Partial<Omit<SeasonalPresentation, "event" | "id" | "season">> & { label: string }> = {
  "new-year": {
    label: "New Year's Day",
    icon: "✦",
    glyphs: ["✦", "✧", "◆", "•"],
    palette: {
      ...SEASONAL.winter.palette,
      background: "#F1F1F5",
      surface: "#FAFAFC",
      surfaceAlt: "#E6E5EC",
      line: "#D3D0DC",
      muted: "#686475",
      quiet: "#9691A2",
      accent: "#8C6A2C",
      accentSoft: "#F0E4C8",
      grid: "rgba(140, 106, 44, .05)",
      ambient:
        "radial-gradient(circle at 50% -8%, rgba(218, 177, 84, .22), transparent 35%), radial-gradient(circle at 88% 72%, rgba(104, 83, 150, .11), transparent 32%)",
      particles: ["#DAB154", "#F0D58B", "#8F74B8", "#FFFFFF", "#A9B8D4"],
    },
  },
  valentine: {
    label: "Valentine's Day",
    icon: "♥",
    glyphs: ["♥", "♡", "✦", "·"],
    palette: {
      ...SEASONAL.winter.palette,
      background: "#F8EFF1",
      surface: "#FFF9FA",
      surfaceAlt: "#F1DFE4",
      line: "#E4C8D0",
      muted: "#775F67",
      quiet: "#A78C95",
      accent: "#C55472",
      accentSoft: "#F3DCE3",
      grid: "rgba(197, 84, 114, .045)",
      ambient: "radial-gradient(circle at 78% 12%, rgba(211, 93, 127, .17), transparent 34%)",
      particles: ["#C55472", "#E18AA1", "#F2B7C6", "#A94766", "#F0D5DD"],
    },
  },
  easter: {
    label: "Easter",
    icon: "🥚",
    glyphs: ["🥚", "✿", "❀", "✦"],
    palette: {
      ...SEASONAL.spring.palette,
      background: "#F7F4EC",
      surface: "#FFFDF8",
      surfaceAlt: "#ECE8D9",
      line: "#DDD7C4",
      muted: "#6F6B5F",
      quiet: "#9E998C",
      accent: "#7B77B5",
      accentSoft: "#E8E5F5",
      grid: "rgba(123, 119, 181, .045)",
      ambient:
        "radial-gradient(circle at 82% 10%, rgba(231, 167, 191, .16), transparent 31%), radial-gradient(circle at 15% 82%, rgba(144, 184, 116, .12), transparent 34%)",
      particles: ["#D98FAA", "#8FB876", "#7B77B5", "#E9C966", "#8EC2CE"],
    },
  },
  "may-day": {
    label: "May Day",
    icon: "✿",
    glyphs: ["✿", "❀", "✦", "·"],
  },
  midsummer: {
    label: "Midsummer",
    icon: "☀",
    glyphs: ["☀", "✦", "✧", "·"],
  },
  "unity-day": {
    label: "German Unity Day",
    icon: "◆",
    glyphs: ["◆", "✦", "·"],
    palette: {
      ...SEASONAL.autumn.palette,
      accent: "#C79522",
      accentSoft: "#F1E5C4",
      ambient:
        "radial-gradient(circle at 82% 10%, rgba(199, 149, 34, .14), transparent 32%), radial-gradient(circle at 12% 82%, rgba(178, 42, 42, .08), transparent 32%)",
      particles: ["#1E1E1E", "#B52D32", "#D5AA38", "#B96932"],
    },
  },
  halloween: {
    label: "Halloween",
    icon: "🎃",
    glyphs: ["🎃", "🦇", "✦", "◆"],
    palette: {
      background: "#17121B",
      surface: "#211927",
      surfaceAlt: "#2B2031",
      line: "#49364F",
      muted: "#B1A1B5",
      quiet: "#7E6E83",
      accent: "#EF8D32",
      accentSoft: "#3B281C",
      grid: "rgba(239, 141, 50, .055)",
      ambient:
        "radial-gradient(circle at 82% 12%, rgba(239, 141, 50, .18), transparent 31%), radial-gradient(circle at 13% 84%, rgba(112, 65, 142, .18), transparent 34%)",
      particles: ["#EF8D32", "#8A55A3", "#D6A24A", "#6F3A80", "#B85831"],
    },
  },
  "st-martin": {
    label: "St. Martin",
    icon: "✦",
    glyphs: ["✦", "◆", "·"],
    palette: {
      ...SEASONAL.autumn.palette,
      accent: "#D0842F",
      accentSoft: "#F3E2C6",
      ambient: "radial-gradient(circle at 80% 14%, rgba(222, 139, 48, .20), transparent 34%)",
      particles: ["#E39A3D", "#D56B34", "#F0C76B", "#8D5C38"],
    },
  },
  advent: {
    label: "Advent",
    icon: "✦",
    glyphs: ["✦", "❄", "·", "✧"],
    palette: {
      ...SEASONAL.winter.palette,
      background: "#F3F1EC",
      surface: "#FCFAF6",
      surfaceAlt: "#E9E4DB",
      line: "#D8D0C5",
      muted: "#69655F",
      quiet: "#98938A",
      accent: "#A84442",
      accentSoft: "#F0DDDA",
      grid: "rgba(168, 68, 66, .045)",
      ambient:
        "radial-gradient(circle at 82% 10%, rgba(168, 68, 66, .13), transparent 31%), radial-gradient(circle at 14% 82%, rgba(43, 105, 75, .10), transparent 33%)",
      particles: ["#B54B49", "#2F7656", "#D6B05E", "#F2E8D4", "#86A99A"],
    },
  },
  "st-nicholas": {
    label: "St. Nicholas Day",
    icon: "🎁",
    glyphs: ["🎁", "❄", "✦", "·"],
  },
  "christmas-eve": {
    label: "Christmas Eve",
    icon: "🎄",
    glyphs: ["❄", "✦", "🎄", "·"],
    palette: {
      background: "#121B19",
      surface: "#192421",
      surfaceAlt: "#22302C",
      line: "#354D45",
      muted: "#A8B7B0",
      quiet: "#74867E",
      accent: "#D8B45D",
      accentSoft: "#342F21",
      grid: "rgba(216, 180, 93, .05)",
      ambient:
        "radial-gradient(circle at 50% -5%, rgba(216, 180, 93, .20), transparent 35%), radial-gradient(circle at 84% 72%, rgba(143, 41, 44, .14), transparent 30%)",
      particles: ["#F6F2E7", "#D8B45D", "#B34748", "#5D9276", "#DCE8E2"],
    },
  },
  christmas: {
    label: "Christmas",
    icon: "🎄",
    glyphs: ["❄", "🎄", "✦", "·"],
    palette: {
      ...SEASONAL.winter.palette,
      background: "#F3F1EA",
      surface: "#FCFAF5",
      surfaceAlt: "#E9E4D9",
      line: "#D7D0C4",
      muted: "#68645D",
      quiet: "#969087",
      accent: "#AA4141",
      accentSoft: "#EFDCDA",
      grid: "rgba(170, 65, 65, .045)",
      ambient:
        "radial-gradient(circle at 82% 10%, rgba(170, 65, 65, .14), transparent 31%), radial-gradient(circle at 13% 82%, rgba(47, 113, 80, .11), transparent 33%)",
      particles: ["#B64848", "#2F7150", "#D4AD54", "#FFFFFF", "#BFD5CC"],
    },
  },
  "new-years-eve": {
    label: "New Year's Eve",
    icon: "✦",
    glyphs: ["✦", "✧", "◆", "•"],
    palette: {
      background: "#111421",
      surface: "#191D2C",
      surfaceAlt: "#22273A",
      line: "#383F59",
      muted: "#A6AABE",
      quiet: "#747A92",
      accent: "#D9B45C",
      accentSoft: "#302B20",
      grid: "rgba(217, 180, 92, .055)",
      ambient:
        "radial-gradient(circle at 50% -5%, rgba(217, 180, 92, .22), transparent 35%), radial-gradient(circle at 88% 76%, rgba(100, 78, 164, .17), transparent 32%)",
      particles: ["#D9B45C", "#F1D98E", "#8E7BC4", "#FFFFFF", "#6DA6C4"],
    },
  },
};

function dayNumber(date: Date): number {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS;
}

function dateAt(year: number, month: number, day: number): Date {
  return new Date(year, month - 1, day, 12, 0, 0, 0);
}

function daysBetween(left: Date, right: Date): number {
  return dayNumber(left) - dayNumber(right);
}

// Gregorian Easter, Meeus/Jones/Butcher algorithm.
export function easterSunday(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return dateAt(year, month, day);
}

function firstAdvent(year: number): Date {
  const christmas = dateAt(year, 12, 25);
  const weekday = christmas.getDay();
  const daysBackToSunday = weekday === 0 ? 7 : weekday;
  const fourthAdvent = new Date(christmas);
  fourthAdvent.setDate(christmas.getDate() - daysBackToSunday);
  const first = new Date(fourthAdvent);
  first.setDate(fourthAdvent.getDate() - 21);
  return first;
}

export function getSeason(date: Date): Season {
  const month = date.getMonth() + 1;
  if (month >= 3 && month <= 5) return "spring";
  if (month >= 6 && month <= 8) return "summer";
  if (month >= 9 && month <= 11) return "autumn";
  return "winter";
}

function getSeasonalEvent(date: Date): SeasonalEvent | null {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();

  if (month === 1 && day === 1) return "new-year";
  if (month === 2 && day === 14) return "valentine";

  const easter = easterSunday(year);
  const easterOffset = daysBetween(date, easter);
  if (easterOffset >= -2 && easterOffset <= 1) return "easter";

  if (month === 5 && day === 1) return "may-day";
  if (month === 6 && day === 21) return "midsummer";
  if (month === 10 && day === 3) return "unity-day";
  if (month === 10 && day >= 25) return "halloween";
  if (month === 11 && day === 11) return "st-martin";

  if (month === 12 && day === 6) return "st-nicholas";
  if (month === 12 && day === 24) return "christmas-eve";
  if (month === 12 && (day === 25 || day === 26)) return "christmas";
  if (month === 12 && day === 31) return "new-years-eve";

  const advent = firstAdvent(year);
  if (daysBetween(date, advent) >= 0 && daysBetween(date, dateAt(year, 12, 23)) <= 0) {
    return "advent";
  }

  return null;
}

export function getSeasonalPresentation(date: Date): SeasonalPresentation {
  const season = getSeason(date);
  const event = getSeasonalEvent(date);
  const base = SEASONAL[season];
  const eventTheme = event ? EVENTS[event] : null;

  return {
    season,
    event,
    id: event ?? season,
    label: eventTheme?.label ?? base.label,
    icon: eventTheme?.icon ?? base.icon,
    glyphs: eventTheme?.glyphs ?? base.glyphs,
    palette: eventTheme?.palette ?? base.palette,
  };
}

export function applySeasonalTheme(
  base: SceneTheme,
  seasonal: SeasonalPresentation,
  mode: string,
): SceneTheme {
  const palette = seasonal.palette;
  const ambient = `${palette.ambient}, ${base.ambient}`;
  const identityCritical = mode === "matchday" || mode === "news" || mode === "gaming" || mode === "media";
  const night = mode === "night";

  if (identityCritical) {
    return {
      ...base,
      ambient,
      particles: {
        ...base.particles,
        colors: [...palette.particles.slice(0, 2), ...base.particles.colors].slice(0, 7),
      },
    };
  }

  if (night) {
    return {
      ...base,
      ambient,
      accent: seasonal.event ? palette.accent : base.accent,
      accentSoft: seasonal.event ? palette.accentSoft : base.accentSoft,
      particles: {
        ...base.particles,
        colors: palette.particles,
        density: Math.min(1.15, base.particles.density ?? 0.8),
        speed: Math.min(0.9, base.particles.speed ?? 0.8),
      },
    };
  }

  if (mode === "development") {
    return {
      ...base,
      ambient,
      particles: {
        ...base.particles,
        colors: [...palette.particles.slice(0, 3), ...base.particles.colors].slice(0, 7),
      },
    };
  }

  return {
    ...base,
    text: ["halloween", "christmas-eve", "new-years-eve"].includes(seasonal.event ?? "") ? "#F3F1EA" : "#242823",
    panel: palette.surface,
    background: palette.background,
    surface: palette.surface,
    surfaceAlt: palette.surfaceAlt,
    line: palette.line,
    muted: palette.muted,
    quiet: palette.quiet,
    accent: palette.accent,
    accentSoft: palette.accentSoft,
    grid: palette.grid,
    ambient,
    particles: {
      colors: palette.particles,
      density: seasonal.event ? 1.08 : 0.86,
      speed: seasonal.id === "halloween" ? 1.08 : seasonal.season === "winter" ? 0.66 : 0.82,
      shape: seasonal.event === "new-years-eve" || seasonal.event === "new-year" ? "confetti" : "mixed",
    },
  };
}
