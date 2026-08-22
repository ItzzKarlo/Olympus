import type { FootballMatchEvent, FootballMatchFlowPoint, FootballTeam } from "../../types/state";

const WIDTH = 1000;
const HEIGHT = 180;
const TOP = 22;
const BOTTOM = 142;
const IMPORTANT_EVENTS = new Set(["goal", "own_goal", "penalty_goal", "yellow_card", "red_card", "second_yellow"]);

function xForMinute(minute: number | null, duration: number): number {
  return 54 + (Math.min(duration, Math.max(0, minute ?? 0)) / duration) * (WIDTH - 108);
}

function yForWeight(weight: number): number {
  return BOTTOM - Math.min(1, Math.max(0, weight)) * (BOTTOM - TOP);
}

function path(points: FootballMatchFlowPoint[], duration: number): string {
  return points.map((point, index) => {
    const x = xForMinute(point.minute, duration);
    const y = yForWeight(point.tracked_team);
    if (index === 0) return `M ${x} ${y}`;
    const previous = points[index - 1];
    const previousX = xForMinute(previous.minute, duration);
    const control = (previousX + x) / 2;
    return `C ${control} ${yForWeight(previous.tracked_team)}, ${control} ${y}, ${x} ${y}`;
  }).join(" ");
}

export function MatchFlow({ events, opponent, points }: {
  events: FootballMatchEvent[];
  opponent: FootballTeam;
  points: FootballMatchFlowPoint[];
}) {
  if (points.length === 0) return null;
  const duration = Math.max(90, ...points.map((point) => point.minute ?? 0), ...events.map((event) => event.minute ?? 0));
  const visibleEvents = events.filter((event) => IMPORTANT_EVENTS.has(event.type) && event.minute != null);
  return (
    <section className="match-flow" aria-label="Olympus-derived Match Flow based on supported match statistics and events; not live ball tracking">
      <header>
        <div><span>Match Flow</span><small>Olympus-derived · not ball position</small></div>
        <div className="match-flow__legend"><span>Bayern</span><span>{opponent.short_name}</span></div>
      </header>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Relative Bayern and opponent match activity over time">
        <line className="match-flow__midline" x1="54" x2={WIDTH - 54} y1="82" y2="82" />
        {duration >= 90 ? <line className="match-flow__halftime" x1={xForMinute(45, duration)} x2={xForMinute(45, duration)} y1="12" y2="154" /> : null}
        <path className="match-flow__opponent" d={path(points.map((point) => ({ ...point, tracked_team: point.opponent })), duration)} />
        <path className="match-flow__tracked" d={path(points, duration)} />
        {visibleEvents.map((event) => (
          <g key={event.id} className={`match-flow__event match-flow__event--${event.type}`} transform={`translate(${xForMinute(event.minute, duration)} 164)`}>
            <circle r={event.type.includes("goal") ? 5 : 3.5} />
            <title>{event.minute}' · {event.player?.name ?? event.type.replaceAll("_", " ")}</title>
          </g>
        ))}
        <text x="54" y="176">0'</text>
        <text className="match-flow__ht-label" x={xForMinute(45, duration)} y="176">HT</text>
        <text x={WIDTH - 54} y="176" textAnchor="end">{duration}'</text>
      </svg>
    </section>
  );
}
