import type { SeasonalPresentation } from "../theme/seasonalTheme";

export function SeasonalLayer({ presentation }: { presentation: SeasonalPresentation }) {
  return <div className={`seasonal-layer seasonal-${presentation.id}`} aria-hidden="true">
    <span className="seasonal-layer__badge">{presentation.label}</span>
  </div>;
}
