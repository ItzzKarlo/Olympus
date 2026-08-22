import type { ActiveAlert, ProbeStatus, RecoveryNotice } from "../types/state";
import { formatElapsed, formatTime } from "../utils/format";

interface Diagnostic {
  label: string;
  status: ProbeStatus;
  latency: number | null;
}

function diagnosticRows(alert: ActiveAlert): Diagnostic[] {
  const labels: Record<string, string> = {
    gateway: "Gateway",
    dns: "DNS",
    internet: "Internet",
    https: "External HTTPS",
  };
  return Object.entries(labels).flatMap(([key, label]) => {
    const value = alert.payload[key];
    if (typeof value !== "object" || value === null || Array.isArray(value)) return [];
    const status = (value as Record<string, unknown>).status;
    const latency = (value as Record<string, unknown>).latency_ms;
    if (status !== "up" && status !== "down" && status !== "unknown") return [];
    return [{ label, status, latency: typeof latency === "number" ? latency : null }];
  });
}

function AlertOverlay({ alert }: { alert: ActiveAlert }) {
  const diagnostics = diagnosticRows(alert);
  return (
    <div className={`event-overlay event-overlay--${alert.severity}`} role="alert">
      <section className="event-overlay__panel">
        <header className="event-overlay__header">
          <span>{alert.type.startsWith("network") ? "Network incident" : "Olympus incident"}</span>
          <span>{alert.severity}</span>
        </header>
        <div className="event-overlay__message">
          <p className="eyebrow">Attention required</p>
          <h2>{alert.title}</h2>
          <p>{alert.message}</p>
        </div>
        {diagnostics.length > 0 ? (
          <div className="event-diagnostics">
            {diagnostics.map((diagnostic) => (
              <div key={diagnostic.label}>
                <span className={`status-pip status-pip--${diagnostic.status}`} aria-hidden="true" />
                <strong>{diagnostic.label}</strong>
                <span>{diagnostic.latency === null ? "—" : `${diagnostic.latency.toFixed(1)} ms`}</span>
                <em>{diagnostic.status}</em>
              </div>
            ))}
          </div>
        ) : null}
        <footer className="event-overlay__footer">
          <span>Source / {alert.source}</span>
          <span>Started {formatTime(new Date(alert.started_at))}</span>
        </footer>
      </section>
    </div>
  );
}

function RecoveryOverlay({ recovery }: { recovery: RecoveryNotice }) {
  return (
    <div className="event-overlay event-overlay--recovery" role="status">
      <section className="recovery-panel">
        <span className="recovery-panel__mark" aria-hidden="true">✓</span>
        <div>
          <p className="eyebrow">Olympus recovery</p>
          <h2>{recovery.title}</h2>
          <p>{recovery.message}</p>
        </div>
        <div className="recovery-panel__downtime">
          <span>Downtime</span>
          <strong>{formatElapsed(recovery.downtime_seconds)}</strong>
        </div>
      </section>
    </div>
  );
}

interface EventOverlayLayerProps {
  alerts: ActiveAlert[];
  now: Date;
  recoveries: RecoveryNotice[];
}

export function EventOverlayLayer({ alerts, now, recoveries }: EventOverlayLayerProps) {
  const activeAlert = alerts[0];
  if (activeAlert) return <AlertOverlay alert={activeAlert} />;
  const recovery = recoveries.filter(
    (item) => Date.parse(item.expires_at) > now.getTime(),
  ).at(-1);
  return recovery ? <RecoveryOverlay recovery={recovery} /> : null;
}
