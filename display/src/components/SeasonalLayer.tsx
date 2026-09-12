import { useMemo } from "react";

import type { SeasonalPresentation } from "../theme/seasonalTheme";

interface SeasonalLayerProps {
  presentation: SeasonalPresentation;
}

interface SeasonalItem {
  delay: string;
  duration: string;
  glyph: string;
  left: string;
  opacity: number;
  scale: number;
  top: string;
}

function seeded(index: number, salt: number): number {
  const value = Math.sin(index * 91.731 + salt * 17.173) * 43758.5453;
  return value - Math.floor(value);
}

export function SeasonalLayer({ presentation }: SeasonalLayerProps) {
  const items = useMemo<SeasonalItem[]>(() => {
    const amount = presentation.event ? 18 : 10;
    return Array.from({ length: amount }, (_, index) => {
      const glyph = presentation.glyphs[index % presentation.glyphs.length];
      return {
        glyph,
        left: `${4 + seeded(index, 1) * 92}%`,
        top: `${4 + seeded(index, 2) * 88}%`,
        delay: `${-seeded(index, 3) * 14}s`,
        duration: `${12 + seeded(index, 4) * 13}s`,
        scale: 0.68 + seeded(index, 5) * 0.62,
        opacity: 0.08 + seeded(index, 6) * 0.12,
      };
    });
  }, [presentation.event, presentation.glyphs]);

  return (
    <div
      className={`seasonal-layer seasonal-${presentation.id}`}
      data-season={presentation.season}
      data-seasonal-event={presentation.event ?? undefined}
      aria-hidden="true"
    >
      <div className="seasonal-layer__halo" />
      {items.map((item, index) => (
        <span
          className="seasonal-layer__item"
          key={`${presentation.id}-${index}`}
          style={{
            "--season-left": item.left,
            "--season-top": item.top,
            "--season-delay": item.delay,
            "--season-duration": item.duration,
            "--season-scale": String(item.scale),
            "--season-opacity": String(item.opacity),
          } as React.CSSProperties}
        >
          {item.glyph}
        </span>
      ))}
      <span className="seasonal-layer__badge">
        <span>{presentation.icon}</span>
        {presentation.label}
      </span>
    </div>
  );
}
