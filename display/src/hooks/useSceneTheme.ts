import { useEffect, useMemo, useState } from "react";

import { fallbackMediaTheme, mediaThemeFromArtwork } from "../theme/mediaPalette";
import { getGamePresentation } from "../modes/Gaming/gameThemes";
import { getMinecraftDimensionTheme } from "../modes/Gaming/minecraftThemes";
import type { SceneTheme } from "../theme/SceneTheme";
import { developmentTheme, idleTheme } from "../theme/themes";
import { getIdleWeatherTheme } from "../theme/idleWeatherTheme";
import { applyNightAdaptation, getNightTheme } from "../theme/nightTheme";
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

  let theme: SceneTheme;
  if (state?.mode === "gaming" && state.gaming) {
    if (state.gaming.game.id === "minecraft" && state.gaming.minecraft) {
      theme = getMinecraftDimensionTheme(state.gaming.minecraft.world.dimension);
    } else {
      theme = getGamePresentation(state.gaming.game.id, state.gaming.game.name).theme;
    }
  } else if (state?.mode === "development") {
    theme = developmentTheme;
  } else if (state?.mode === "media") {
    theme = mediaTheme?.theme ?? initialFallback;
  } else if (state?.mode === "night") {
    return getNightTheme(state.weather?.current?.condition);
  } else if (state?.mode === "idle" && state.weather?.available) {
    theme = getIdleWeatherTheme(state.weather.current?.condition);
  } else {
    theme = idleTheme;
  }

  return state?.time_policy.is_night ? applyNightAdaptation(theme) : theme;
}
