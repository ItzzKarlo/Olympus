import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import { usePlaybackProgress } from "../../hooks/usePlaybackProgress";
import type { ConnectionStatus as Status, MediaState } from "../../types/state";
import { formatDuration } from "../../utils/format";

interface MediaModeProps {
  connectionStatus: Status;
  media: MediaState;
}

function contextLabel(media: MediaState): string {
  if (media.context) {
    const type = media.context.type.charAt(0).toUpperCase() + media.context.type.slice(1);
    if (media.context.name) return `${type} · ${media.context.name}`;
    return type;
  }
  return media.track?.album?.name ? `Album · ${media.track.album.name}` : "Now playing";
}

export function MediaMode({ connectionStatus, media }: MediaModeProps) {
  const track = media.track;
  const progress = usePlaybackProgress(media);
  if (!track) return null;

  const artwork = track.album?.artwork_url;
  const progressPercent = track.duration_ms
    ? Math.min(100, (progress / track.duration_ms) * 100)
    : 0;

  return (
    <section className="scene scene--media">
      {artwork ? (
        <div className="media-artwork-backdrop" aria-hidden="true">
          <img src={artwork} alt="" />
        </div>
      ) : null}
      <header className="scene__header media-header">
        <Brand />
        <div className="media-header__status">
          <span className="media-live"><i aria-hidden="true" /> Spotify / Live</span>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>

      <div className="media-stage">
        <div className="media-artwork-wrap">
          <span className="media-orbit media-orbit--outer" aria-hidden="true" />
          <span className="media-orbit media-orbit--inner" aria-hidden="true" />
          <div className="media-artwork">
            {artwork ? (
              <img
                key={artwork}
                src={artwork}
                alt={`${track.album?.name ?? track.title} artwork`}
              />
            ) : (
              <span className="media-artwork__fallback" aria-hidden="true">O</span>
            )}
          </div>
        </div>

        <div className="media-content">
          <p className="eyebrow media-context">{contextLabel(media)}</p>
          <h1>{track.title}</h1>
          <p className="media-artists">
            {track.artists.map((artist) => artist.name).join(", ") || "Unknown artist"}
          </p>
          {track.album ? <p className="media-album">{track.album.name}</p> : null}

          <div className="media-progress" aria-label="Playback progress">
            <div className="media-progress__track">
              <span style={{ width: `${progressPercent}%` }} />
            </div>
            <div className="media-progress__time">
              <time>{formatDuration(progress)}</time>
              <time>{formatDuration(track.duration_ms)}</time>
            </div>
          </div>

          <div className="media-queue">
            <div className="media-queue__heading">
              <span>Next up</span>
              <span>{media.queue.length.toString().padStart(2, "0")} queued</span>
            </div>
            {media.queue.length > 0 ? (
              <ol>
                {media.queue.map((queuedTrack, index) => (
                  <li key={queuedTrack.id ?? `${queuedTrack.title}-${index}`}>
                    <span>{(index + 1).toString().padStart(2, "0")}</span>
                    <div>
                      <strong>{queuedTrack.title}</strong>
                      <small>{queuedTrack.artists.join(", ") || "Unknown artist"}</small>
                    </div>
                    <time>{formatDuration(queuedTrack.duration_ms)}</time>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="media-queue__empty">The queue is quiet after this track.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
