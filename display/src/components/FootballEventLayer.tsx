import type { CSSProperties } from "react";

import type { FootballDisplayEvent, OlympusState } from "../types/state";

type ParticleStyle = CSSProperties & Record<`--${string}`, string>;

export function FootballEventLayer({ events, state }: { events: FootballDisplayEvent[]; state: OlympusState }) {
  const context = state.football?.matchday;
  if (!context) return null;
  return (
    <div className="football-event-layer" aria-live="assertive">
      {events.map((message) => {
        const event = message.payload.event;
        if (message.type === "football.goal" && event) {
          const tracked = event.for_tracked_team;
          return (
            <div key={message.id} className={`football-reaction football-reaction--goal football-reaction--${tracked ? "tracked" : "opponent"}`}>
              {tracked ? <div className="football-goal-burst" aria-hidden="true">{Array.from({ length: 18 }, (_, index) => <i key={index} style={{ "--burst-index": `${index}` } as ParticleStyle} />)}</div> : null}
              <div className="football-reaction__message">
                <span>{tracked ? "FC Bayern München" : event.team?.short_name ?? "Opponent"}</span>
                <strong>{tracked ? "GOAL" : "Opponent goal"}</strong>
                <small>{event.player?.name ?? "Score updated"} · {event.minute ?? "—"}'</small>
              </div>
            </div>
          );
        }
        if (["football.yellow_card", "football.red_card", "football.substitution", "football.var"].includes(message.type) && event) {
          return (
            <div key={message.id} className={`football-reaction football-reaction--callout football-reaction--${event.type}`}>
              <span>{event.type.replaceAll("_", " ")}</span>
              <strong>{event.player?.name ?? event.team?.short_name ?? "Match update"}</strong>
              <small>{event.team?.short_name} · {event.minute ?? "—"}'</small>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}
