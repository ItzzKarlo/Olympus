import type { OlympusState, ProbeStatus } from "../types/state";

interface AmbientItem {
  id: string;
  label: string;
  status: ProbeStatus;
}

export function AmbientStatus({ state }: { state: OlympusState }) {
  const items: AmbientItem[] = [];
  if (state.core_host) {
    items.push({ id: "core", label: state.core_host.hostname, status: "up" });
  }
  if (state.network) {
    items.push({ id: "internet", label: "Internet", status: state.network.internet.status });
    items.push(
      ...Object.values(state.network.targets).slice(0, 2).map((target) => ({
        id: target.id,
        label: target.name,
        status: target.status,
      })),
    );
  }
  items.push(
    ...Object.values(state.services).slice(0, Math.max(0, 4 - items.length)).map((service) => ({
      id: service.id,
      label: service.name,
      status: service.status,
    })),
  );
  if (items.length === 0) return null;
  return (
    <div className="ambient-status" aria-label="Olympus system status">
      {items.slice(0, 4).map((item) => (
        <span key={item.id}>
          <i className={`status-pip status-pip--${item.status}`} aria-hidden="true" />
          {item.label}
        </span>
      ))}
    </div>
  );
}
