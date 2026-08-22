import type { CSSProperties } from "react";

import type { FootballDisplayEvent, OlympusState } from "../types/state";

type ParticleStyle = CSSProperties & Record<`--${string}`, string>;

export function FootballEventLayer({ events, state }: { events: FootballDisplayEvent[]; state: OlympusState }) {
  const context = state.football?.matchday;
  if (!context || state.alerts.some((alert) => alert.severity === "critical")) return null;
  return (
    <div className="football-event-layer" aria-live="assertive">
      {events.map((message) => {
        const event = message.payload.event;
        if (message.type === "football.goal" && event) {
          const tracked = event.for_tracked_team;
          const performance = context.player_statistics.find((player) =>
            (event.player?.id && player.player.id === event.player.id) || player.player.name === event.player?.name);
          const score = context.match.score;
          return (
            <div key={message.id} className={`football-reaction football-reaction--goal football-reaction--${tracked ? "tracked" : "opponent"}`}>
              {tracked ? <div className="football-goal-burst" aria-hidden="true">{Array.from({ length: 18 }, (_, index) => <i key={index} style={{ "--burst-index": `${index}` } as ParticleStyle} />)}</div> : null}
              <div className="football-reaction__message">
                <span>{tracked ? "FC Bayern München" : event.team?.short_name ?? "Opponent"}</span>
                <strong>{tracked ? "GOAL" : "Opponent goal"}</strong>
                <b className="football-reaction__score">{context.match.home.short_name} {score.home ?? "—"} — {score.away ?? "—"} {context.match.away.short_name}</b>
                <small>{event.player?.name ?? "Score updated"} · {event.minute ?? "—"}'{event.assist ? ` · Assist ${event.assist.name}` : ""}{performance?.rating != null ? ` · Rating ${performance.rating.toFixed(1)}` : ""}</small>
              </div>
            </div>
          );
        }
        if (message.type === "football.player.rating_changed" && message.payload.player) {
          const delta = message.payload.delta;
          return (
            <div key={message.id} className="football-reaction football-reaction--callout football-reaction--rating">
              <span>Watched player · rating update</span>
              <strong>{message.payload.player.name}</strong>
              <small>{message.payload.previous_rating?.toFixed(1)} → {message.payload.rating?.toFixed(1)} {delta != null ? `${delta > 0 ? "▲" : "▼"}${Math.abs(delta).toFixed(1)}` : ""}</small>
            </div>
          );
        }
        if (["football.yellow_card", "football.red_card", "football.substitution", "football.var"].includes(message.type) && event) {
          const substitution = message.type === "football.substitution" && event.assist;
          return (
            <div key={message.id} className={`football-reaction football-reaction--callout football-reaction--${event.type}`}>
              <span>{event.type.replaceAll("_", " ")}</span>
              <strong>{substitution ? `${event.assist?.name} ↑` : event.player?.name ?? event.team?.short_name ?? "Match update"}</strong>
              {substitution ? <b>{event.player?.name} ↓</b> : null}
              <small>{event.team?.short_name} · {event.minute ?? "—"}'</small>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
