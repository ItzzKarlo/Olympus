import { Brand } from "../../components/Brand";
import { AmbientStatus } from "../../components/AmbientStatus";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import { NextMatchAmbient } from "../../components/NextMatchAmbient";
import type { CalendarEvent, ConnectionStatus as Status, OlympusState } from "../../types/state";
import {
  formatDate,
  formatEventTime,
  formatRelativeEvent,
  formatTemperature,
  formatTime,
  formatWeatherCondition,
} from "../../utils/format";

interface IdleModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

function currentEvents(events: CalendarEvent[], now: Date): CalendarEvent[] {
  return events.filter((event) => event.all_day || !event.end || new Date(event.end).getTime() > now.getTime());
}

function nextEvent(events: CalendarEvent[], now: Date): CalendarEvent | null {
  const relevant = currentEvents(events, now);
  return relevant.find((event) => event.status === "ongoing") ?? relevant[0] ?? null;
}

function staleLabel(observedAt: string, now: Date): string {
  const minutes = Math.max(1, Math.round((now.getTime() - new Date(observedAt).getTime()) / 60_000));
  return `updated ${minutes}m ago`;
}

function Agenda({ events, label, limit, now, timezone }: {
  events: CalendarEvent[];
  label: string;
  limit: number;
  now: Date;
  timezone: string;
}) {
  const relevant = currentEvents(events, now);
  const visible = relevant.slice(0, limit);
  if (visible.length === 0) return null;
  return (
    <section className="idle-agenda" aria-label={`${label} calendar`}>
      <header><span>{label}</span>{relevant.length > limit ? <small>+{relevant.length - limit} more</small> : null}</header>
      <ol>
        {visible.map((event) => (
          <li key={event.id} className={event.status === "ongoing" ? "idle-agenda__event--ongoing" : ""}>
            <time dateTime={event.start ?? event.start_date ?? undefined}>
              {event.status === "ongoing" && !event.all_day ? "Now" : formatEventTime(event.start, event.all_day, timezone)}
            </time>
            <div><strong>{event.title}</strong>{event.location ? <small>{event.location}</small> : null}</div>
            {event.calendar_name ? <span>{event.calendar_name}</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function IdleMode({ connectionStatus, now, state }: IdleModeProps) {
  const weather = state.weather?.available ? state.weather : null;
  const calendar = state.calendar?.available ? state.calendar : null;
  const upcoming = calendar ? nextEvent(calendar.events, now) : null;
  const minutesUntil = upcoming?.start
    ? (new Date(upcoming.start).getTime() - now.getTime()) / 60_000
    : Number.POSITIVE_INFINITY;
  const urgency = upcoming?.status === "ongoing" || minutesUntil <= 15
    ? "now"
    : minutesUntil <= 60 ? "soon" : "normal";
  const condition = weather?.current?.condition ?? "unknown";

  return (
    <section className="scene scene--idle scene--ambient-idle" data-weather={condition}>
      <header className="scene__header">
        <Brand />
        <ConnectionStatus status={connectionStatus} />
      </header>

      <div className="ambient-idle-stage">
        <div className="ambient-idle-hero">
          <div className="ambient-clock">
            <p className="eyebrow">Room state / Ambient</p>
            <time className="ambient-clock__time" dateTime={now.toISOString()}>
              {formatTime(now, state.timezone)}
            </time>
            <p className="ambient-clock__date">{formatDate(now, state.timezone)}</p>
          </div>

          {weather?.current ? (
            <section className="ambient-weather" aria-label="Current weather">
              <div className="ambient-weather__current">
                {weather.current.temperature_c != null ? <strong>{formatTemperature(weather.current.temperature_c)}</strong> : null}
                <div>
                  <span>{formatWeatherCondition(weather.current.condition)}</span>
                  <small>{weather.location.name ?? "Configured home location"}</small>
                </div>
              </div>
              <div className="ambient-weather__details">
                {weather.current.apparent_temperature_c != null ? <span>Feels like {formatTemperature(weather.current.apparent_temperature_c)}</span> : null}
                {weather.current.precipitation_probability != null ? <span>{weather.current.precipitation_probability}% rain</span> : null}
                {weather.today?.high_c != null && weather.today.low_c != null ? <span>High {formatTemperature(weather.today.high_c)} · Low {formatTemperature(weather.today.low_c)}</span> : null}
              </div>
              {weather.tomorrow ? (
                <p className="ambient-weather__tomorrow">
                  Tomorrow · {formatWeatherCondition(weather.tomorrow.condition)}
                  {weather.tomorrow.high_c != null ? ` · ${formatTemperature(weather.tomorrow.high_c)}` : ""}
                </p>
              ) : null}
              {weather.stale ? <p className="ambient-source-stale">Weather · {staleLabel(weather.observed_at, now)}</p> : null}
            </section>
          ) : null}
        </div>

        {upcoming ? (
          <section className={`ambient-next ambient-next--${urgency}`} aria-label="Next calendar event">
            <p className="eyebrow">{upcoming.status === "ongoing" ? "Happening now" : "Next"}</p>
            <strong>{upcoming.title}</strong>
            <div>
              <time dateTime={upcoming.start ?? upcoming.start_date ?? undefined}>
                {formatEventTime(upcoming.start, upcoming.all_day, state.timezone)}
              </time>
              <span>{upcoming.all_day ? upcoming.calendar_name : formatRelativeEvent(upcoming.start, upcoming.end, upcoming.status, now)}</span>
            </div>
          </section>
        ) : null}

        <NextMatchAmbient
          match={state.football?.next_match ?? null}
          now={now}
          trackedTeamId={state.football?.tracked_team.id ?? ""}
          timezone={state.timezone}
        />

        {calendar && (calendar.today.length > 0 || calendar.tomorrow.length > 0) ? (
          <div className="ambient-calendar">
            <Agenda events={calendar.today} label="Today" limit={4} now={now} timezone={state.timezone} />
            <Agenda events={calendar.tomorrow} label="Tomorrow" limit={3} now={now} timezone={state.timezone} />
            {calendar.stale ? <p className="ambient-source-stale ambient-source-stale--calendar">Calendar · {staleLabel(calendar.observed_at, now)}</p> : null}
          </div>
        ) : null}
      </div>

      <AmbientStatus state={state} />
    </section>
  );
}
