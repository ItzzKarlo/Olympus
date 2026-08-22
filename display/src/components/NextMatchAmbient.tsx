import type { FootballMatch } from "../types/state";
import { formatTime } from "../utils/format";

function localDateKey(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: timezone }).format(date);
}

function dateLabel(kickoff: Date, now: Date, timezone: string): string {
  const today = localDateKey(now, timezone);
  const tomorrow = localDateKey(new Date(now.getTime() + 86_400_000), timezone);
  const target = localDateKey(kickoff, timezone);
  if (target === today) return "Today";
  if (target === tomorrow) return "Tomorrow";
  return new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", timeZone: timezone }).format(kickoff);
}

export function NextMatchAmbient({ match, now, timezone, trackedTeamId, compact = false }: {
  compact?: boolean;
  match: FootballMatch | null;
  now: Date;
  trackedTeamId: string;
  timezone: string;
}) {
  if (!match || new Date(match.kickoff).getTime() <= now.getTime()) return null;
  const trackedHome = match.home.id === trackedTeamId;
  const opponent = trackedHome ? match.away.short_name : match.home.short_name;
  return (
    <section className={`ambient-football${compact ? " ambient-football--compact" : ""}`} aria-label="Next Bayern match">
      <span>Next match</span>
      <strong>Bayern {trackedHome ? "vs" : "at"} {opponent}</strong>
      <small>{dateLabel(new Date(match.kickoff), now, timezone)} · {formatTime(new Date(match.kickoff), timezone)}</small>
    </section>
  );
}
