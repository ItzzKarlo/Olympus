import { useEffect, useState } from "react";

import type { MediaState } from "../types/state";

function projectedProgress(media: MediaState): number {
  const duration = media.track?.duration_ms ?? 0;
  if (!media.is_playing) return Math.min(media.progress_ms, duration);
  const observed = Date.parse(media.observed_at);
  const elapsed = Number.isFinite(observed) ? Math.max(0, Date.now() - observed) : 0;
  return Math.min(media.progress_ms + elapsed, duration);
}

export function usePlaybackProgress(media: MediaState): number {
  const [progress, setProgress] = useState(() => projectedProgress(media));

  useEffect(() => {
    const update = () => setProgress(projectedProgress(media));
    update();
    if (!media.is_playing) return;
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [media]);

  return progress;
}
