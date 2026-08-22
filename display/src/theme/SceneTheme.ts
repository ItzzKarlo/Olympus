import type { CSSProperties } from "react";

export interface SceneTheme {
  background: string;
  ambient: string;
  surface: string;
  surfaceAlt: string;
  panel: string;
  line: string;
  muted: string;
  quiet: string;
  text: string;
  accent: string;
  accentSoft: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  grid: string;
  particles: string[];
}

export type SceneStyle = CSSProperties & Record<`--${string}`, string>;

export function sceneStyle(theme: SceneTheme): SceneStyle {
  return {
    "--background": theme.background,
    "--ambient": theme.ambient,
    "--surface": theme.surface,
    "--surface-alt": theme.surfaceAlt,
    "--panel": theme.panel,
    "--line": theme.line,
    "--muted": theme.muted,
    "--quiet": theme.quiet,
    "--text": theme.text,
    "--accent": theme.accent,
    "--accent-soft": theme.accentSoft,
    "--success": theme.success,
    "--warning": theme.warning,
    "--danger": theme.danger,
    "--info": theme.info,
    "--idle": theme.accent,
    "--development": theme.accent,
    "--grid": theme.grid,
  };
}
