import type { MachineState } from "../types/state";
import { formatMemory, formatPercent, formatPlatform } from "../utils/format";

interface MachineCardProps {
  machine: MachineState;
  active?: boolean;
}

export function MachineCard({ machine, active = false }: MachineCardProps) {
  return (
    <article
      className={`machine-card${machine.online ? "" : " machine-card--offline"}${active ? " machine-card--active" : ""}`}
    >
      <div className="machine-card__identity">
        <span className="machine-card__status" aria-hidden="true" />
        <div>
          <h3>{machine.hostname}</h3>
          <p>
            {formatPlatform(machine.platform)} {machine.platform_version}
          </p>
        </div>
      </div>

      <div className="machine-card__reading">
        <span>CPU</span>
        <strong>
          {machine.system ? formatPercent(machine.system.cpu_percent) : "—"}
        </strong>
      </div>
      <div className="machine-card__reading machine-card__reading--memory">
        <span>Memory</span>
        <strong>
          {machine.system
            ? formatMemory(
                machine.system.ram_used_bytes,
                machine.system.ram_total_bytes,
              )
            : "Awaiting telemetry"}
        </strong>
      </div>
      <div className="machine-card__activity">
        <span>{machine.online ? "Online" : "Offline"}</span>
        {machine.online && machine.activity?.application ? (
          <strong>{machine.activity.application}</strong>
        ) : null}
      </div>
    </article>
  );
}
