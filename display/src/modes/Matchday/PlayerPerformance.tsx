import type { FootballPlayerStatistics, MatchPhase, WatchedPlayerState } from "../../types/state";

function ratingBand(rating: number | null): string {
  if (rating == null) return "unrated";
  if (rating >= 9) return "exceptional";
  if (rating >= 8) return "excellent";
  if (rating >= 7) return "good";
  if (rating >= 6) return "average";
  return "poor";
}

function meaningfulStats(statistics: FootballPlayerStatistics | null): string[] {
  if (!statistics) return [];
  const values: string[] = [];
  if ((statistics.goals ?? 0) > 0) values.push(`${statistics.goals} ${statistics.goals === 1 ? "goal" : "goals"}`);
  if ((statistics.assists ?? 0) > 0) values.push(`${statistics.assists} ${statistics.assists === 1 ? "assist" : "assists"}`);
  if (statistics.shots.total != null) values.push(`${statistics.shots.total} shots${statistics.shots.on_target != null ? ` · ${statistics.shots.on_target} on target` : ""}`);
  if ((statistics.passes.key ?? 0) > 0) values.push(`${statistics.passes.key} key passes`);
  if ((statistics.dribbles.successful ?? 0) > 0) values.push(`${statistics.dribbles.successful} successful dribbles`);
  if (statistics.duels.won != null && statistics.duels.total != null) values.push(`${statistics.duels.won}/${statistics.duels.total} duels won`);
  if (statistics.passes.accuracy_percent != null) values.push(`${Math.round(statistics.passes.accuracy_percent)}% passing`);
  return values.slice(0, 3);
}

function PlayerCard({ watched }: { watched: WatchedPlayerState }) {
  const stats = meaningfulStats(watched.statistics);
  const delta = watched.rating_delta;
  return (
    <article className={`player-card player-rating--${ratingBand(watched.rating)}`}>
      <header>
        <div><span>{watched.player.number ?? "—"}</span><strong>{watched.player.name}</strong></div>
        {watched.rating != null ? (
          <div className="player-card__rating">
            <strong>{watched.rating.toFixed(1)}</strong>
            {delta != null && delta !== 0 ? <small className={delta > 0 ? "rating-up" : "rating-down"}>{delta > 0 ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}</small> : null}
          </div>
        ) : <small className="player-card__status">{watched.status.replaceAll("_", " ")}</small>}
      </header>
      {watched.rating != null ? <p className="player-card__source">Provider performance rating · {watched.status}</p> : null}
      {stats.length > 0 ? <ul>{stats.map((value) => <li key={value}>{value}</li>)}</ul> : null}
    </article>
  );
}

function PerformerList({ players, title }: { players: FootballPlayerStatistics[]; title: string }) {
  if (players.length === 0) return null;
  return (
    <section className="top-performers">
      <p className="eyebrow">{title}</p>
      <ol>{players.map((player, index) => (
        <li key={player.player.id ?? player.player.name}>
          <span>{index + 1}</span><strong>{player.player.name}</strong><b className={`player-rating--${ratingBand(player.rating)}`}>{player.rating?.toFixed(1)}</b>
        </li>
      ))}</ol>
    </section>
  );
}

export function PlayerPerformance({ phase, topOpponent, topTracked, watched }: {
  phase: MatchPhase;
  topOpponent: FootballPlayerStatistics[];
  topTracked: FootballPlayerStatistics[];
  watched: WatchedPlayerState[];
}) {
  const showWatched = watched.length > 0;
  if (!showWatched && topTracked.length === 0 && topOpponent.length === 0) return null;
  const final = phase === "post_match" || phase === "finished";
  return (
    <section className="player-performance" aria-label="Player performance ratings">
      <header><span>{showWatched ? "Watched players" : final ? "Top rated players" : "Current top rated"}</span><small>Provider ratings</small></header>
      {showWatched ? <div className="player-performance__cards">{watched.slice(0, 3).map((player) => <PlayerCard key={player.player.id ?? player.player.name} watched={player} />)}</div> : null}
      <div className="player-performance__leaders">
        <PerformerList players={topTracked.slice(0, 3)} title={final ? "Top rated Bayern" : "Current top rated Bayern"} />
        {final ? <PerformerList players={topOpponent.slice(0, 1)} title="Top rated opponent" /> : null}
      </div>
    </section>
  );
}
