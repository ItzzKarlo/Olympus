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
  uptime_seconds: number | null;
}

export interface StorageTelemetry {
  root_used_percent: number;
  root_free_bytes: number;
  root_total_bytes: number;
}

export interface NetworkTelemetry {
  bytes_sent: number;
  bytes_received: number;
}

export interface TemperatureTelemetry {
  cpu_celsius: number | null;
  gpu_celsius: number | null;
}

export interface GpuTelemetry {
  name: string;
  utilization_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
  temperature_celsius: number | null;
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
  storage: StorageTelemetry | null;
  network: NetworkTelemetry | null;
  temperatures: TemperatureTelemetry | null;
  gpu: GpuTelemetry | null;
  activity: ActivityTelemetry | null;
}

export type ProbeStatus = "up" | "down" | "unknown";

export interface ProbeState {
  status: ProbeStatus;
  latency_ms: number | null;
  last_checked: string | null;
}

export interface NetworkTargetState extends ProbeState {
  id: string;
  name: string;
}

export interface NetworkState {
  gateway: ProbeState;
  dns: ProbeState;
  internet: ProbeState;
  https: ProbeState;
  targets: Record<string, NetworkTargetState>;
}

export interface ServiceState {
  id: string;
  name: string;
  status: ProbeStatus;
  latency_ms: number | null;
  last_checked: string | null;
  last_changed: string | null;
}

export interface CoreHostState {
  hostname: string;
  platform: string;
  observed_at: string;
  system: SystemTelemetry;
  storage: StorageTelemetry;
}

export type EventSeverity = "info" | "warning" | "critical";

export interface ActiveAlert {
  id: string;
  incident_key: string;
  type: string;
  severity: EventSeverity;
  title: string;
  message: string;
  source: string;
  started_at: string;
  payload: Record<string, unknown>;
}

export interface RecoveryNotice {
  id: string;
  incident_key: string;
  type: string;
  title: string;
  message: string;
  source: string;
  recovered_at: string;
  downtime_seconds: number;
  expires_at: string;
  payload: Record<string, unknown>;
}

export interface MediaArtist {
  id: string | null;
  name: string;
}

export interface MediaAlbum {
  id: string | null;
  name: string;
  artwork_url: string | null;
}

export interface MediaTrack {
  id: string | null;
  title: string;
  artists: MediaArtist[];
  duration_ms: number;
  album: MediaAlbum | null;
}

export interface MediaContext {
  type: string;
  name: string | null;
  uri: string | null;
}

export interface MediaQueueTrack {
  id: string | null;
  title: string;
  artists: string[];
  duration_ms: number;
  artwork_url: string | null;
}

export interface MediaState {
  provider: "spotify";
  available: boolean;
  is_playing: boolean;
  observed_at: string;
  progress_ms: number;
  track: MediaTrack | null;
  context: MediaContext | null;
  queue: MediaQueueTrack[];
}

export interface OlympusState {
  type: "state";
  mode: ActivityMode;
  active_device: string | null;
  generated_at: string;
  machines: Record<string, MachineState>;
  media: MediaState | null;
  core_host: CoreHostState | null;
  network: NetworkState | null;
  services: Record<string, ServiceState>;
  alerts: ActiveAlert[];
  recoveries: RecoveryNotice[];
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting";
