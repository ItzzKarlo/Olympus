import type { ConnectionStatus as Status } from "../types/state";

interface ConnectionStatusProps {
  status: Status;
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const labels: Record<Status, string> = {
    connecting: "Connecting to Core",
    connected: "Core online",
    reconnecting: "Reconnecting to Core",
  };

  return (
    <div className={`connection-status connection-status--${status}`} aria-live="polite">
      <span className="connection-status__dot" aria-hidden="true" />
      <span>{labels[status]}</span>
    </div>
  );
}
