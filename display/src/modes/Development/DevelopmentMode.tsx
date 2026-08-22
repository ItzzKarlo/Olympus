import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import { MachineCard } from "../../components/MachineCard";
import { MetricBar } from "../../components/MetricBar";
import type { ConnectionStatus as Status, OlympusState } from "../../types/state";
import { formatMemory, formatTime } from "../../utils/format";

interface DevelopmentModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

export function DevelopmentMode({
  connectionStatus,
  now,
  state,
}: DevelopmentModeProps) {
  const machines = Object.values(state.machines);
  const activeMachine = state.active_device
    ? state.machines[state.active_device]
    : undefined;

  return (
    <section className="scene scene--development">
      <header className="scene__header">
        <Brand />
        <div className="development-header__right">
          <span className="development-header__mode">Development</span>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>

      <div className="development-focus">
        <div className="development-focus__identity">
          <p className="eyebrow">Active workstation</p>
          <h1>{activeMachine?.hostname ?? "Development session"}</h1>
          <p className="development-focus__application">
            {activeMachine?.activity?.application ?? "IDE active"}
          </p>
        </div>
        <time className="development-focus__time" dateTime={now.toISOString()}>
          {formatTime(now)}
        </time>
      </div>

      <div className="development-metrics">
        {activeMachine?.system ? (
          <>
            <MetricBar
              label="Processor"
              percentage={activeMachine.system.cpu_percent}
              detail="Current system load"
            />
            <MetricBar
              label="Memory"
              percentage={activeMachine.system.ram_percent}
              detail={formatMemory(
                activeMachine.system.ram_used_bytes,
                activeMachine.system.ram_total_bytes,
              )}
            />
          </>
        ) : (
          <p className="empty-state">Waiting for workstation telemetry.</p>
        )}
      </div>

      <div className="device-section device-section--development">
        <div className="section-heading">
          <span>Olympus devices</span>
          <span>{machines.length} registered</span>
        </div>
        <div className="machine-list">
          {machines.map((machine) => (
            <MachineCard
              key={machine.agent_id}
              machine={machine}
              active={machine.agent_id === state.active_device}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
