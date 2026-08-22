import type { NewsCluster } from "../types/state";
import { formatRelativeNews } from "../utils/format";

function attribution(story: NewsCluster): string {
  if (story.sources.length === 0) return "Publisher feed";
  if (story.sources.length === 1) return story.sources[0].name;
  return `${story.sources.length} sources`;
}

export function AmbientNews({ compact = false, now, stories }: {
  compact?: boolean;
  now: Date;
  stories: NewsCluster[];
}) {
  const visible = stories.slice(0, compact ? 1 : 3);
  if (visible.length === 0) return null;
  return (
    <section className={`ambient-news${compact ? " ambient-news--compact" : ""}`} aria-label="Latest news">
      <header><span>Latest</span><small>Publisher feeds</small></header>
      <ol>{visible.map((story) => {
        const representative = story.articles[0];
        return (
          <li key={story.id} data-topic={story.topic}>
            <i aria-hidden="true" />
            <div>
              <strong lang={story.language}>{story.headline}</strong>
              <small>{attribution(story)} · {formatRelativeNews(representative?.published_at ?? null, representative?.observed_at ?? story.latest_seen_at, now)}</small>
            </div>
          </li>
        );
      })}</ol>
    </section>
  );
}
