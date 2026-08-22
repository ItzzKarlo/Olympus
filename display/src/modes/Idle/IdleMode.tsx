import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import { MachineCard } from "../../components/MachineCard";
import type { ConnectionStatus as Status, OlympusState } from "../../types/state";
import { formatDate, formatTime } from "../../utils/format";

interface IdleModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

export function IdleMode({ connectionStatus, now, state }: IdleModeProps) {
  const machines = Object.values(state.machines);

  return (
    <section className="scene scene--idle">
      <header className="scene__header">
        <Brand />
        <ConnectionStatus status={connectionStatus} />
      </header>

      <div className="idle-focus">
        <p className="eyebrow">Room state / Idle</p>
        <time className="idle-focus__time" dateTime={now.toISOString()}>
          {formatTime(now)}
        </time>
        <p className="idle-focus__date">{formatDate(now)}</p>
      </div>

      <div className="device-section">
        <div className="section-heading">
          <span>Olympus devices</span>
          <span>{machines.filter((machine) => machine.online).length} online</span>
        </div>
        <div className="machine-list">
          {machines.length > 0 ? (
            machines.map((machine) => (
              <MachineCard key={machine.agent_id} machine={machine} />
            ))
          ) : (
            <p className="empty-state">Waiting for the first Olympus agent.</p>
          )}
        </div>
      </div>
    </section>
  );
}
