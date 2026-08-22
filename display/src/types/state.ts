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
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting";
