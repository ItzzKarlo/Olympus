import type { NetworkState, ProbeState } from "../types/state";
import { formatLatency } from "../utils/format";

interface NetworkPanelProps {
  network: NetworkState | null;
}

export function NetworkPanel({ network }: NetworkPanelProps) {
  if (!network) return null;
  const rows: { id: string; label: string; state: ProbeState }[] = [
    { id: "gateway", label: "Gateway", state: network.gateway },
    { id: "dns", label: "DNS", state: network.dns },
    { id: "internet", label: "Internet", state: network.internet },
    { id: "https", label: "External HTTPS", state: network.https },
    ...Object.values(network.targets).map((target) => ({
      id: target.id,
      label: target.name,
      state: target,
    })),
  ];
  return (
    <section className="network-panel">
      <div className="section-heading">
        <span>Network</span>
        <span>Live diagnostics</span>
      </div>
      <div className="network-panel__rows">
        {rows.map((row) => (
          <div key={row.id}>
            <span className={`status-pip status-pip--${row.state.status}`} aria-hidden="true" />
            <strong>{row.label}</strong>
            <span>{formatLatency(row.state.latency_ms)}</span>
            <em>{row.state.status}</em>
          </div>
        ))}
      </div>
    </section>
  );
}
