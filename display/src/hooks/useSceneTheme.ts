import { useEffect, useMemo, useState } from "react";

import { fallbackMediaTheme, mediaThemeFromArtwork } from "../theme/mediaPalette";
import type { SceneTheme } from "../theme/SceneTheme";
import { developmentTheme, idleTheme } from "../theme/themes";
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

  if (state?.mode === "development") return developmentTheme;
  if (state?.mode === "media") return mediaTheme?.theme ?? initialFallback;
  return idleTheme;
}
