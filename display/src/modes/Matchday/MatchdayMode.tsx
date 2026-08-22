import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type {
  ConnectionStatus as Status,
  FootballMatch,
  FootballMatchEvent,
  FootballTeamStatistics,
  MatchdayContext,
  OlympusState,
} from "../../types/state";
import { formatTime } from "../../utils/format";

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
  const goals = events.filter((event) => event.team?.id === teamId && GOALS.has(event.type)).slice(-3);
  if (goals.length === 0) return null;
  return (
    <ul className="matchday-team-goals">
      {goals.map((event) => <li key={event.id}>{event.player?.name ?? "Goal"} <span>{minuteLabel(event)}</span></li>)}
    </ul>
  );
}

function Statistics({ context }: { context: MatchdayContext }) {
  const statistics = context.statistics;
  if (!statistics?.home || !statistics.away) return null;
  const rows: Array<[string, keyof FootballTeamStatistics]> = [
    ["Possession", "possession_percent"],
    ["Shots", "shots"],
    ["On target", "shots_on_target"],
    ["Corners", "corners"],
  ];
  const visible = rows.filter(([, field]) => statistics.home?.[field] != null || statistics.away?.[field] != null).slice(0, 3);
  if (visible.length === 0) return null;
  return (
    <section className="matchday-stats" aria-label="Match statistics">
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
  const visible = events.filter((event) => event.type !== "unknown").slice(-4).reverse();
  if (visible.length === 0) return null;
  return (
    <section className="matchday-events" aria-label="Recent match events">
      <p className="eyebrow">Recent events</p>
      <ol>
        {visible.map((event) => (
          <li key={event.id}>
            <time>{minuteLabel(event)}</time>
            <i className={`matchday-event-mark matchday-event-mark--${event.type}`} aria-hidden="true" />
            <div><strong>{event.player?.name ?? event.detail ?? "Match event"}</strong><small>{event.team?.short_name ?? "Match"} · {event.type.replaceAll("_", " ")}</small></div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PreMatch({ context, now, timezone }: { context: MatchdayContext; now: Date; timezone: string }) {
  const match = context.match;
  const trackedHome = match.home.id === context.tracked_team.id;
  const opponent = trackedHome ? match.away : match.home;
  const trackedLineup = trackedHome ? context.lineups?.home : context.lineups?.away;
  const starters = trackedLineup?.players.filter((player) => player.starter).slice(0, 11) ?? [];
  return (
    <div className="matchday-prematch-stage">
      <div className="matchday-prematch-hero">
        <p className="eyebrow">Matchday / Pre-match</p>
        <div className="matchday-versus">
          <strong>Bayern</strong><span>vs</span><strong>{opponent.short_name}</strong>
        </div>
        <p>{match.competition.name}{match.venue ? ` · ${match.venue.name}` : ""}</p>
      </div>
      <div className="matchday-kickoff">
        <span>Kickoff</span>
        <time dateTime={match.kickoff}>{formatTime(new Date(match.kickoff), timezone)}</time>
        <small>Starts in {countdown(match, now)}</small>
      </div>
      {starters.length > 0 ? (
        <section className="matchday-lineup" aria-label="Bayern starting lineup">
          <header><span>Starting XI</span>{trackedLineup?.formation ? <small>{trackedLineup.formation}</small> : null}</header>
          <ol>{starters.map((player) => <li key={player.id ?? player.name}><span>{player.number ?? "—"}</span>{player.name}<small>{player.position}</small></li>)}</ol>
        </section>
      ) : null}
    </div>
  );
}

function LiveMatch({ context }: { context: MatchdayContext }) {
  const match = context.match;
  return (
    <div className="matchday-live-stage">
      <div className="matchday-scoreboard">
        <div className="matchday-team matchday-team--home">
          <p>Home</p><h1>{match.home.short_name}</h1><TeamGoals events={context.events} teamId={match.home.id} />
        </div>
        <div className="matchday-score">
          <span>{clockLabel(context)}</span>
          <strong>{match.score.home ?? "—"}<i>—</i>{match.score.away ?? "—"}</strong>
          <small>{context.phase === "post_match" ? "Full time" : context.phase === "half_time" ? "Half time" : "Live score"}</small>
        </div>
        <div className="matchday-team matchday-team--away">
          <p>Away</p><h1>{match.away.short_name}</h1><TeamGoals events={context.events} teamId={match.away.id} />
        </div>
      </div>
      <div className="matchday-detail-grid">
        <Statistics context={context} />
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
    <section className={`scene scene--matchday matchday-phase--${context.phase}`}>
      <header className="scene__header matchday-header">
        <Brand />
        <div className="matchday-header__context">
          <span>{context.match.competition.name}</span>
          <strong>{preMatch ? "Matchday" : clockLabel(context)}</strong>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>
      {preMatch ? <PreMatch context={context} now={now} timezone={state.timezone} /> : <LiveMatch context={context} />}
      {context.stale || state.football?.stale || !state.football?.available ? (
        <p className="matchday-stale">Live data delayed · Last update {formatTime(new Date(context.observed_at), state.timezone)}</p>
      ) : null}
    </section>
  );
}
