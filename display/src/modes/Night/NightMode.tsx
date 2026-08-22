import { AmbientStatus } from "../../components/AmbientStatus";
import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type { CalendarEvent, ConnectionStatus as Status, OlympusState } from "../../types/state";
import {
  formatDate,
  formatEventTime,
  formatRelativeEvent,
  formatTemperature,
  formatTime,
  formatWeatherCondition,
} from "../../utils/format";

interface NightModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

function EventTime({ event, timezone }: { event: CalendarEvent; timezone: string }) {
  return (
    <time dateTime={event.start ?? event.start_date ?? undefined}>
      {event.status === "ongoing" && !event.all_day
        ? "Now"
        : formatEventTime(event.start, event.all_day, timezone)}
    </time>
  );
}

export function NightMode({ connectionStatus, now, state }: NightModeProps) {
  const weather = state.weather?.available ? state.weather : null;
  const calendar = state.calendar?.available ? state.calendar : null;
  const nextEvent = calendar?.next_event ?? calendar?.tomorrow[0] ?? null;
  const tomorrow = calendar?.tomorrow.slice(0, 3) ?? [];

  return (
    <section className="scene scene--night" data-weather={weather?.current?.condition ?? "unknown"}>
      <header className="scene__header">
        <Brand />
        <ConnectionStatus status={connectionStatus} />
      </header>

      <div className="night-stage">
        <div className="night-primary">
          <p className="eyebrow">Room state / Night</p>
          <time className="night-clock" dateTime={now.toISOString()}>
            {formatTime(now, state.timezone)}
          </time>
          <p className="night-date">{formatDate(now, state.timezone)}</p>

          {weather?.current ? (
            <section className="night-weather" aria-label="Current weather">
              {weather.current.temperature_c != null ? (
                <strong>{formatTemperature(weather.current.temperature_c)}</strong>
              ) : null}
              <div>
                <span>{formatWeatherCondition(weather.current.condition)}</span>
                {weather.tomorrow ? (
                  <small>
                    Tomorrow · {formatWeatherCondition(weather.tomorrow.condition)}
                    {weather.tomorrow.high_c != null ? ` · ${formatTemperature(weather.tomorrow.high_c)}` : ""}
                  </small>
                ) : null}
              </div>
            </section>
          ) : null}
        </div>

        {(nextEvent || tomorrow.length > 0) ? (
          <aside className="night-agenda" aria-label="Night calendar summary">
            {nextEvent ? (
              <section className="night-next">
                <p className="eyebrow">{nextEvent.status === "ongoing" ? "Happening now" : "Next"}</p>
                <h1>{nextEvent.title}</h1>
                <div>
                  <EventTime event={nextEvent} timezone={state.timezone} />
                  <span>{formatRelativeEvent(nextEvent.start, nextEvent.end, nextEvent.status, now)}</span>
                </div>
              </section>
            ) : null}

            {tomorrow.length > 0 ? (
              <section className="night-tomorrow">
                <header>
                  <span>Tomorrow</span>
                  {calendar && calendar.tomorrow.length > 3 ? <small>+{calendar.tomorrow.length - 3} more</small> : null}
                </header>
                <ol>
                  {tomorrow.map((event) => (
                    <li key={event.id}>
                      <EventTime event={event} timezone={state.timezone} />
                      <div>
                        <strong>{event.title}</strong>
                        {event.location ? <small>{event.location}</small> : null}
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </aside>
        ) : null}
      </div>

      <AmbientStatus state={state} />
    </section>
  );
}
