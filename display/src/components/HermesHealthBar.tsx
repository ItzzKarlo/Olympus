import type { ConnectionStatus, OlympusState, ProbeStatus } from "../types/state";

function statusClass(status: ProbeStatus | ConnectionStatus): string {
  if (status === "connected" || status === "up") return "up";
  if (status === "down") return "down";
  return "unknown";
}

export function HermesHealthBar({ connectionStatus, state }: {
  connectionStatus: ConnectionStatus;
  state: OlympusState;
}) {
  const host = state.core_host;
  const machines = Object.values(state.machines);
  const onlineAgents = machines.filter((machine) => machine.online).length;
  const services = Object.values(state.services);
  const servicesDown = services.filter((service) => service.status === "down").length;
  const network = state.network;
  const powerWarning = host?.throttled || host?.undervoltage;

  return (
    <aside className={`hermes-health${powerWarning ? " hermes-health--warning" : ""}`} aria-label="Hermes health">
      <span className="hermes-health__name">Hermes</span>
      <span><i className={`status-pip status-pip--${statusClass(connectionStatus)}`} />Core</span>
      {host ? <>
        <span>CPU {Math.round(host.system.cpu_percent)}%</span>
        <span>RAM {Math.round(host.system.ram_percent)}%</span>
        <span>Disk {Math.round(host.storage.root_used_percent)}%</span>
        {host.cpu_temperature_celsius == null ? null : <span>{Math.round(host.cpu_temperature_celsius)}°C</span>}
        {(host.swap_percent ?? 0) > 0 ? <span>Swap {Math.round(host.swap_percent ?? 0)}%</span> : null}
      </> : <span>Host telemetry pending</span>}
      {network ? <span><i className={`status-pip status-pip--${statusClass(network.internet.status)}`} />Net</span> : null}
      <span>{onlineAgents}/{machines.length} Agents</span>
      {services.length ? <span className={servicesDown ? "hermes-health__problem" : ""}>{servicesDown ? `${servicesDown} service down` : `${services.length} services`}</span> : null}
      {host?.undervoltage ? <span className="hermes-health__problem">Undervoltage</span> : null}
      {host?.throttled ? <span className="hermes-health__problem">Throttled</span> : null}
    </aside>
  );
}
