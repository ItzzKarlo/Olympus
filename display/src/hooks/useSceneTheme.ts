import { useEffect, useMemo, useState } from "react";

import { fallbackMediaTheme, mediaThemeFromArtwork } from "../theme/mediaPalette";
import { getGamePresentation } from "../modes/Gaming/gameThemes";
import { getMinecraftDimensionTheme } from "../modes/Gaming/minecraftThemes";
import type { SceneTheme } from "../theme/SceneTheme";
import { developmentTheme, idleTheme } from "../theme/themes";
import { getIdleWeatherTheme } from "../theme/idleWeatherTheme";
import type { OlympusState } from "../types/state";

interface ResolvedMediaTheme {
  key: string;
  theme: SceneTheme;
}

export function useSceneTheme(state: OlympusState | null): SceneTheme {
  const track = state?.media?.track;
  const key = track?.id ?? track?.album?.id ?? track?.title ?? "olympus-media";
  const artworkUrl = track?.album?.artwork_url ?? null;
  const initialFallback = useMemo(() => fallbackMediaTheme(key), [key]);
  const [mediaTheme, setMediaTheme] = useState<ResolvedMediaTheme | null>(null);

  useEffect(() => {
    if (!track) return;
    let cancelled = false;
    void mediaThemeFromArtwork(artworkUrl, key).then((theme) => {
      if (!cancelled) setMediaTheme({ key, theme });
    });
    return () => {
      cancelled = true;
    };
  }, [artworkUrl, key]);

  if (state?.mode === "gaming" && state.gaming) {
    if (state.gaming.game.id === "minecraft" && state.gaming.minecraft) {
      return getMinecraftDimensionTheme(state.gaming.minecraft.world.dimension);
    }
    return getGamePresentation(state.gaming.game.id, state.gaming.game.name).theme;
  }
  if (state?.mode === "development") return developmentTheme;
  if (state?.mode === "media") return mediaTheme?.theme ?? initialFallback;
  if (state?.mode === "idle" && state.weather?.available) {
    return getIdleWeatherTheme(state.weather.current?.condition);
  }
  return idleTheme;
}
