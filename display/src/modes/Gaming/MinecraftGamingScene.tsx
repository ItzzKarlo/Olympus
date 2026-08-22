import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type { ConnectionStatus as Status, MachineState, MinecraftState } from "../../types/state";
import { formatSessionDuration } from "../../utils/format";
import { formatMinecraftIdentifier } from "./minecraftThemes";

interface MinecraftGamingSceneProps {
  connectionStatus: Status;
  machine?: MachineState;
  minecraft: MinecraftState;
  now: Date;
  sessionStartedAt: string;
}

interface VitalProps {
  label: string;
  max?: number | null;
  value: number;
}

function clampPercentage(value: number, max: number): number {
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function Vital({ label, max, value }: VitalProps) {
  const scale = max && max > 0 ? max : label === "Armor" ? 20 : Math.max(value, 1);
  return (
    <div className="minecraft-vital">
      <div className="minecraft-vital__label">
        <span>{label}</span>
        <strong>{Number.isInteger(value) ? value : value.toFixed(1)}{max ? ` / ${max}` : ""}</strong>
      </div>
      <div className="minecraft-vital__track" aria-label={`${label} ${value}${max ? ` of ${max}` : ""}`}>
        <span style={{ width: `${clampPercentage(value, scale)}%` }} />
      </div>
    </div>
  );
}

function rounded(value: number | null): string {
  return value == null ? "—" : Math.round(value).toLocaleString();
}

export function MinecraftGamingScene({ connectionStatus, machine, minecraft, now, sessionStartedAt }: MinecraftGamingSceneProps) {
  const { connection, player, world } = minecraft;
  const startedAt = Date.parse(sessionStartedAt);
  const sessionSeconds = Number.isFinite(startedAt) ? Math.max(0, (now.getTime() - startedAt) / 1000) : 0;
  const place = connection.server_name || connection.world_name || (connection.type === "multiplayer" ? "Multiplayer server" : "Singleplayer world");
  const dimension = formatMinecraftIdentifier(world.dimension);
  const biome = formatMinecraftIdentifier(world.biome);
  const vitals = [
    player.health == null ? null : <Vital key="health" label="Health" max={player.max_health} value={player.health} />,
    player.food == null ? null : <Vital key="food" label="Food" max={player.max_food} value={player.food} />,
    player.armor == null ? null : <Vital key="armor" label="Armor" value={player.armor} />,
  ].filter(Boolean);

  return (
    <section className={`scene scene--gaming scene--minecraft ${minecraft.low_health ? "scene--minecraft-low-health" : ""}`} data-dimension={world.dimension}>
      <div className="minecraft-atmosphere" aria-hidden="true"><i /><i /><i /><i /></div>
      <header className="scene__header gaming-header">
        <Brand />
        <div className="gaming-header__status">
          <span className="gaming-live"><i aria-hidden="true" /> Minecraft / {dimension}</span>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>

      <div className="minecraft-stage">
        <div className="minecraft-place">
          <p className="eyebrow">Olympus Minecraft observer</p>
          <h1>{place}</h1>
          <p className="minecraft-context">{player.game_mode} <i aria-hidden="true" /> {dimension}</p>
          <p className="minecraft-biome">{biome}</p>
        </div>

        <div className="minecraft-coordinates" aria-label="Player coordinates">
          <div><span>X</span><strong>{rounded(player.position.x)}</strong></div>
          <div><span>Y</span><strong>{rounded(player.position.y)}</strong></div>
          <div><span>Z</span><strong>{rounded(player.position.z)}</strong></div>
        </div>

        {vitals.length ? <div className="minecraft-vitals">{vitals}</div> : null}

        <div className="minecraft-footer">
          {player.experience ? (
            <div className="minecraft-stat">
              <span>XP</span>
              <strong>Level {player.experience.level ?? "—"}</strong>
              {player.experience.progress != null ? <small>{Math.round(player.experience.progress * 100)}% toward next level</small> : null}
            </div>
          ) : null}
          <div className="minecraft-stat">
            <span>Session</span>
            <strong>{formatSessionDuration(sessionSeconds)}</strong>
            <small>{connection.type}</small>
          </div>
          <div className="minecraft-stat minecraft-stat--machine">
            <span>Observed by</span>
            <strong>{machine?.hostname ?? "Active machine"}</strong>
            <small>{machine?.online === false ? "Agent offline" : "Local Fabric integration"}</small>
          </div>
        </div>
      </div>
    </section>
  );
}
