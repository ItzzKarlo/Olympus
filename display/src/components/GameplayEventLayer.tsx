import type { GameplayEvent } from "../types/state";

interface GameplayEventLayerProps {
  events: GameplayEvent[];
}

function eventKind(type: string): string {
  if (type.endsWith("damage_taken") || type.endsWith("low_health")) return "damage";
  if (type.endsWith("healed")) return "healing";
  if (type.endsWith("died")) return "death";
  if (type.endsWith("dimension.changed")) return "dimension";
  return "session";
}

export function GameplayEventLayer({ events }: GameplayEventLayerProps) {
  return (
    <div className="gameplay-event-layer" aria-live="polite">
      {events.map((event) => {
        const kind = eventKind(event.type);
        const destination = typeof event.payload.to === "string" ? event.payload.to : null;
        return (
          <div key={event.id} className={`gameplay-event gameplay-event--${kind}`}>
            {kind === "death" ? (
              <div className="gameplay-event__death">
                <span>Olympus observation</span>
                <strong>Player down</strong>
                <small>Waiting for the world to resume</small>
              </div>
            ) : kind === "session" ? (
              <span className="gameplay-event__notice">
                {event.type.endsWith("joined") ? "World joined" : "World left"}
              </span>
            ) : kind === "dimension" && destination ? (
              <span className="gameplay-event__notice">Entering {destination.replace("minecraft:", "").replaceAll("_", " ")}</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
