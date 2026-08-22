export type ActivityMode =
  | "idle"
  | "development"
  | "gaming"
  | "media"
  | "unknown";

export interface SystemTelemetry {
  cpu_percent: number;
  ram_percent: number;
  ram_used_bytes: number;
  ram_total_bytes: number;
}

export interface ActivityTelemetry {
  mode: ActivityMode;
  application: string | null;
  process_name: string | null;
}

export interface MachineState {
  agent_id: string;
  hostname: string;
  platform: string;
  platform_version: string;
  online: boolean;
  last_seen: string;
  system: SystemTelemetry | null;
  activity: ActivityTelemetry | null;
}

export interface OlympusState {
  type: "state";
  mode: ActivityMode;
  active_device: string | null;
  generated_at: string;
  machines: Record<string, MachineState>;
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting";
