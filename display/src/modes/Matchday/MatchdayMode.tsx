import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type {
  ConnectionStatus as Status,
  FootballLineupPlayer,
  FootballMatch,
  FootballMatchEvent,
  FootballTeamLineup,
  FootballTeamStatistics,
  MatchdayContext,
  OlympusState,
} from "../../types/state";
import { formatTime } from "../../utils/format";
import { MatchFlow } from "./MatchFlow";
import { PlayerPerformance } from "./PlayerPerformance";

interface MatchdayModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

const GOALS = new Set(["goal", "own_goal", "penalty_goal"]);

function minuteLabel(event: FootballMatchEvent): string {
  if (event.minute == null) return "—";
  return `${event.minute}${event.added_time ? `+${event.added_time}` : ""}'`;
}

function clockLabel(context: MatchdayContext): string {
  if (context.phase === "half_time") return "HT";
  if (context.phase === "post_match" || context.phase === "finished") return "FT";
  if (context.phase === "suspended") return "SUSP";
  const clock = context.match.clock;
  if (clock?.minute == null) return context.phase === "live" ? "LIVE" : "MATCHDAY";
  return `${clock.minute}${clock.added_time ? `+${clock.added_time}` : ""}'`;
}

function countdown(match: FootballMatch, now: Date): string {
  const minutes = Math.max(0, Math.ceil((new Date(match.kickoff).getTime() - now.getTime()) / 60_000));
  if (minutes < 60) return `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function TeamGoals({ events, teamId }: { events: FootballMatchEvent[]; teamId: string }) {
  const goals = events.filter((event) => event.team?.id === teamId && GOALS.has(event.type)).slice(-4);
  if (goals.length === 0) return null;
  return <ul className="matchday-team-goals">{goals.map((event) => <li key={event.id}>{event.player?.name ?? "Goal"} <span>{minuteLabel(event)}</span></li>)}</ul>;
}

function Statistics({ context }: { context: MatchdayContext }) {
  const statistics = context.statistics;
  if (!statistics?.home || !statistics.away) return null;
  const rows: Array<[string, keyof FootballTeamStatistics]> = [
    ["Possession", "possession_percent"], ["Shots", "shots"], ["On target", "shots_on_target"],
    ["Corners", "corners"], ["Pass accuracy", "pass_accuracy_percent"], ["Fouls", "fouls"],
  ];
  const visible = rows.filter(([, field]) => statistics.home?.[field] != null || statistics.away?.[field] != null).slice(0, 5);
  if (visible.length === 0) return null;
  return (
    <section className="matchday-stats" aria-label="Key team statistics">
      <p className="eyebrow">Key team stats</p>
      {visible.map(([label, field]) => (
        <div key={field}>
          <strong>{statistics.home?.[field] ?? "—"}{field.includes("percent") && statistics.home?.[field] != null ? "%" : ""}</strong>
          <span>{label}</span>
          <strong>{statistics.away?.[field] ?? "—"}{field.includes("percent") && statistics.away?.[field] != null ? "%" : ""}</strong>
        </div>
      ))}
    </section>
  );
}

function RecentEvents({ events }: { events: FootballMatchEvent[] }) {
  const visible = events.filter((event) => event.type !== "unknown").slice(-5).reverse();
  if (visible.length === 0) return null;
  return (
    <section className="matchday-events" aria-label="Recent match events">
      <p className="eyebrow">Recent events</p>
      <ol>{visible.map((event) => (
        <li key={event.id}>
          <time>{minuteLabel(event)}</time>
          <i className={`matchday-event-mark matchday-event-mark--${event.type}`} aria-hidden="true" />
          <div>
            <strong>{event.type === "substitution" && event.assist ? `${event.assist.name} ↑ · ${event.player?.name ?? "Player"} ↓` : event.player?.name ?? event.detail ?? "Match event"}</strong>
            <small>{event.team?.short_name ?? "Match"} · {event.type.replaceAll("_", " ")}</small>
          </div>
        </li>
      ))}</ol>
    </section>
  );
}

const POSITION_LABELS: Record<string, string> = { G: "Goalkeeper", D: "Defence", M: "Midfield", F: "Attack" };

function groupedStarters(lineup: FootballTeamLineup): Array<[string, FootballLineupPlayer[]]> {
  const groups = new Map<string, FootballLineupPlayer[]>();
  lineup.players.filter((player) => player.starter).forEach((player) => {
    const position = player.position?.charAt(0).toUpperCase() || "?";
    groups.set(position, [...(groups.get(position) ?? []), player]);
  });
  return ["G", "D", "M", "F", "?"].flatMap((position) => groups.has(position) ? [[POSITION_LABELS[position] ?? "Other", groups.get(position)!] as [string, FootballLineupPlayer[]]] : []);
}

function LineupPanel({ lineup, tracked, watchedIds }: { lineup: FootballTeamLineup; tracked: boolean; watchedIds: Set<string> }) {
  return (
    <section className={`matchday-lineup-board${tracked ? " matchday-lineup-board--tracked" : ""}`} aria-label={`${lineup.team.short_name} starting lineup`}>
      <header><div><span>{tracked ? "Bayern Starting XI" : `${lineup.team.short_name} XI`}</span><strong>{lineup.team.short_name}</strong></div>{lineup.formation ? <small>{lineup.formation}</small> : null}</header>
      <div className="matchday-lineup-groups">{groupedStarters(lineup).map(([position, players]) => (
        <div key={position}><span>{position}</span><p>{players.map((player, index) => (
          <span key={player.id ?? player.name}><strong className={player.id && watchedIds.has(player.id) ? "lineup-player--watched" : ""}>{player.name}{player.id && watchedIds.has(player.id) ? " ●" : ""}</strong>{index < players.length - 1 ? <i> · </i> : null}</span>
        ))}</p></div>
      ))}</div>
    </section>
  );
}

function PreMatch({ context, now, timezone }: { context: MatchdayContext; now: Date; timezone: string }) {
  const match = context.match;
  const trackedHome = match.home.id === context.tracked_team.id;
  const opponent = trackedHome ? match.away : match.home;
  const watchedIds = new Set(context.watched_players.flatMap((watched) => watched.player.id ? [watched.player.id] : []));
  return (
    <div className={`matchday-prematch-stage${context.lineups ? " matchday-prematch-stage--lineups" : ""}`}>
      <div className="matchday-prematch-top">
        <div className="matchday-prematch-hero">
          <p className="eyebrow">Matchday / Pre-match</p>
          <div className="matchday-versus"><strong>Bayern</strong><span>vs</span><strong>{opponent.short_name}</strong></div>
          <p>{match.competition.name}{match.venue ? ` · ${match.venue.name}` : ""}</p>
        </div>
        <div className="matchday-kickoff"><span>Kickoff</span><time dateTime={match.kickoff}>{formatTime(new Date(match.kickoff), timezone)}</time><small>Starts in {countdown(match, now)}</small></div>
      </div>
      {context.lineups?.home && context.lineups.away ? (
        <div className="matchday-lineups">
          <LineupPanel lineup={context.lineups.home} tracked={context.lineups.home.team.id === context.tracked_team.id} watchedIds={watchedIds} />
          <div className="matchday-lineups__versus">VS</div>
          <LineupPanel lineup={context.lineups.away} tracked={context.lineups.away.team.id === context.tracked_team.id} watchedIds={watchedIds} />
        </div>
      ) : null}
      {context.watched_players.length > 0 ? <div className="prematch-watched">{context.watched_players.map((watched) => <span key={watched.player.id ?? watched.player.name}><i />{watched.player.name}<small>{watched.status === "unavailable" ? "not in squad" : watched.status}</small></span>)}</div> : null}
    </div>
  );
}

function phaseSummary(context: MatchdayContext): string {
  if (context.phase === "half_time") return "Half-time analysis";
  if (context.phase === "post_match" || context.phase === "finished") {
    return context.result === "win" ? "Bayern win" : context.result === "loss" ? "Full-time summary" : context.result === "draw" ? "Match drawn" : "Full time";
  }
  return "Live match center";
}

function LiveMatch({ context }: { context: MatchdayContext }) {
  const match = context.match;
  const opponent = match.home.id === context.tracked_team.id ? match.away : match.home;
  return (
    <div className={`matchday-live-stage matchday-result--${context.result}`}>
      <div className="matchday-scoreboard">
        <div className="matchday-team matchday-team--home"><p>Home</p><h1>{match.home.short_name}</h1><TeamGoals events={context.events} teamId={match.home.id} /></div>
        <div className="matchday-score"><span>{clockLabel(context)}</span><strong>{match.score.home ?? "—"}<i>—</i>{match.score.away ?? "—"}</strong><small>{phaseSummary(context)}</small></div>
        <div className="matchday-team matchday-team--away"><p>Away</p><h1>{match.away.short_name}</h1><TeamGoals events={context.events} teamId={match.away.id} /></div>
      </div>
      <MatchFlow events={context.events} opponent={opponent} points={context.match_flow} />
      <div className="matchday-analytics-grid">
        <Statistics context={context} />
        <PlayerPerformance phase={context.phase} watched={context.watched_players} topTracked={context.top_tracked_players} topOpponent={context.top_opponent_players} />
        <RecentEvents events={context.events} />
      </div>
    </div>
  );
}

export function MatchdayMode({ connectionStatus, now, state }: MatchdayModeProps) {
  const context = state.football?.matchday;
  if (!context) return null;
  const preMatch = context.phase === "pre_match";
  return (
    <section className={`scene scene--matchday matchday-phase--${context.phase} matchday-result--${context.result}`}>
      <header className="scene__header matchday-header">
        <Brand />
        <div className="matchday-header__context"><span>{context.match.competition.name}</span><strong>{preMatch ? "Matchday" : clockLabel(context)}</strong><ConnectionStatus status={connectionStatus} /></div>
      </header>
      {preMatch ? <PreMatch context={context} now={now} timezone={state.timezone} /> : <LiveMatch context={context} />}
      {context.stale || state.football?.stale || !state.football?.available ? <p className="matchday-stale">Live data delayed · Last update {formatTime(new Date(context.observed_at), state.timezone)}</p> : null}
    </section>
  );
}
