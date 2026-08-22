import type { CSSProperties } from "react";

import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type { ConnectionStatus as Status, NewsCluster, OlympusState } from "../../types/state";
import { formatRelativeNews, formatTime } from "../../utils/format";

function sourceLabel(story: NewsCluster): string {
  const names = story.sources.slice(0, 3).map((source) => source.name);
  if (story.sources.length > 3) names.push(`+${story.sources.length - 3}`);
  return names.join(" · ") || "Publisher feed";
}

export function NewsMode({ connectionStatus, now, state }: {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}) {
  const story = state.news?.active_story;
  const presentation = state.news?.presentation;
  if (!story || !presentation) return null;
  const representative = story.articles[0];
  const duration = Math.max(1, new Date(presentation.ends_at).getTime() - new Date(presentation.started_at).getTime());
  const remaining = Math.max(0, new Date(presentation.ends_at).getTime() - now.getTime());
  const progress = Math.min(1, remaining / duration);
  const style = { "--news-remaining": `${progress * 100}%` } as CSSProperties;
  const major = presentation.level === "major";

  return (
    <section className={`scene scene--news news-level--${presentation.level}`} data-topic={story.topic} style={style}>
      <header className="scene__header news-header">
        <Brand />
        <div className="news-header__status">
          <span>{major ? "Major development" : "Developing"}</span>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>

      <div className="news-stage">
        <aside className="news-index" aria-label="Story context">
          <span className="news-index__number">{major ? "01" : "N"}</span>
          <div><span>Topic</span><strong>{story.topic}</strong></div>
          <div><span>Coverage</span><strong>{story.sources.length === 1 ? "1 source" : `${story.sources.length} sources`}</strong></div>
          <div><span>Room context</span><strong>Temporary</strong></div>
        </aside>

        <article className="news-story">
          <p className="eyebrow">{major ? "Major news" : "News context"} / {story.topic}</p>
          <h1 lang={story.language}>{story.headline}</h1>
          {story.summary ? <p className="news-story__summary" lang={story.language}>{story.summary}</p> : null}
          <footer>
            <div><span>Reported by</span><strong>{sourceLabel(story)}</strong></div>
            <div><span>Updated</span><strong>{formatRelativeNews(representative?.published_at ?? null, representative?.observed_at ?? story.latest_seen_at, now)}</strong></div>
            <time dateTime={story.latest_seen_at}>{formatTime(new Date(story.latest_seen_at), state.timezone)}</time>
          </footer>
        </article>
      </div>

      <div className="news-progress" aria-hidden="true"><i /></div>
      <p className="news-attribution">Publisher-provided headline{story.summary ? " and summary" : ""} · Olympus does not author or rewrite this story</p>
    </section>
  );
}
