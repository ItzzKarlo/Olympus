import { formatPercent } from "../utils/format";

interface MetricBarProps {
  label: string;
  percentage: number;
  detail?: string;
}

export function MetricBar({ label, percentage, detail }: MetricBarProps) {
  const safePercentage = Math.min(100, Math.max(0, percentage));

  return (
    <div className="metric">
      <div className="metric__header">
        <span className="metric__label">{label}</span>
        <span className="metric__value">{formatPercent(safePercentage)}</span>
      </div>
      <div
        className="metric__track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(safePercentage)}
      >
        <span className="metric__fill" style={{ width: `${safePercentage}%` }} />
      </div>
      {detail ? <span className="metric__detail">{detail}</span> : null}
    </div>
  );
}
