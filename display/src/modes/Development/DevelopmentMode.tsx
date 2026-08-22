import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import { MachineCard } from "../../components/MachineCard";
import { MetricBar } from "../../components/MetricBar";
import { NetworkPanel } from "../../components/NetworkPanel";
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
  const temperature =
    activeMachine?.gpu?.temperature_celsius ??
    activeMachine?.temperatures?.gpu_celsius ??
    activeMachine?.temperatures?.cpu_celsius;

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
            {activeMachine.gpu?.utilization_percent !== null &&
            activeMachine.gpu?.utilization_percent !== undefined ? (
              <MetricBar
                label="Graphics"
                percentage={activeMachine.gpu.utilization_percent}
                detail={activeMachine.gpu.name}
              />
            ) : null}
            {activeMachine.storage ? (
              <MetricBar
                label="Disk"
                percentage={activeMachine.storage.root_used_percent}
                detail={formatMemory(
                  activeMachine.storage.root_total_bytes - activeMachine.storage.root_free_bytes,
                  activeMachine.storage.root_total_bytes,
                )}
              />
            ) : null}
            {temperature !== null && temperature !== undefined ? (
              <div className="metric metric--reading">
                <span className="metric__label">
                  {activeMachine.gpu?.temperature_celsius != null ? "GPU temperature" : "CPU temperature"}
                </span>
                <strong>{Math.round(temperature)}°C</strong>
                <span className="metric__detail">Live thermal reading</span>
              </div>
            ) : null}
          </>
        ) : (
          <p className="empty-state">Waiting for workstation telemetry.</p>
        )}
      </div>

      <div className="development-awareness">
        <NetworkPanel network={state.network} />
        <div className="device-section device-section--development">
          <div className="section-heading">
            <span>Olympus system</span>
            <span>
              {state.core_host ? "Core online" : "Core observing"} · {machines.length} agents
            </span>
          </div>
          <div className="machine-list">
            {state.core_host ? (
              <div className="core-host-row">
                <div>
                  <span className="status-pip status-pip--up" aria-hidden="true" />
                  <strong>{state.core_host.hostname}</strong>
                  <small>Olympus Core host</small>
                </div>
                <span>CPU {Math.round(state.core_host.system.cpu_percent)}%</span>
                <span>RAM {Math.round(state.core_host.system.ram_percent)}%</span>
                <span>Disk {Math.round(state.core_host.storage.root_used_percent)}%</span>
              </div>
            ) : null}
            {machines.map((machine) => (
              <MachineCard
                key={machine.agent_id}
                machine={machine}
                active={machine.agent_id === state.active_device}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
