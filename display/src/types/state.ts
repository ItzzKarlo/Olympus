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

export interface GameInfo {
  id: string;
  name: string;
}

export interface ActivityTelemetry {
  mode: ActivityMode;
  application: string | null;
  process_name: string | null;
  game: GameInfo | null;
  fps: number | null;
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

export interface GatewayProbeState extends ProbeState {
  host: string | null;
  source: string;
}

export interface NetworkTargetState extends ProbeState {
  id: string;
  name: string;
}

export interface NetworkState {
  gateway: GatewayProbeState;
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

export interface GamingState {
  game: GameInfo;
  session_started_at: string;
  fps: number | null;
  integration: GamingIntegration | null;
  minecraft: MinecraftState | null;
}

export interface IntegrationObserver {
  id: string;
  name: string;
  version: string;
}

export interface GamingIntegration {
  type: string;
  available: boolean;
  connected: boolean;
  last_seen: string;
  observer: IntegrationObserver;
}

export interface MinecraftConnection {
  type: "singleplayer" | "multiplayer";
  server_name: string | null;
  server_address: string | null;
  world_name: string | null;
}

export interface MinecraftPosition {
  x: number | null;
  y: number | null;
  z: number | null;
}

export interface MinecraftExperience {
  level: number | null;
  progress: number | null;
}

export interface MinecraftPlayer {
  position: MinecraftPosition;
  health: number | null;
  max_health: number | null;
  food: number | null;
  max_food: number | null;
  armor: number | null;
  experience: MinecraftExperience | null;
  game_mode: "survival" | "creative" | "adventure" | "spectator" | "unknown";
}

export interface MinecraftState {
  connection: MinecraftConnection;
  world: { dimension: string; biome: string };
  player: MinecraftPlayer;
  observed_at: string;
  low_health: boolean;
}

export interface GameplayEvent {
  id: string;
  type: string;
  category: "gameplay";
  severity: "info" | "warning" | "critical";
  timestamp: string;
  source: { agent_id: string; integration: string };
  payload: Record<string, unknown>;
}

export interface DisplayEventMessage {
  type: "event";
  event: GameplayEvent;
}

export type WeatherCondition =
  | "clear" | "mostly_clear" | "partly_cloudy" | "cloudy" | "fog"
  | "drizzle" | "rain" | "heavy_rain" | "snow" | "thunderstorm" | "unknown";

export interface WeatherLocation {
  latitude: number;
  longitude: number;
  timezone: string;
  name: string | null;
}

export interface CurrentWeather {
  temperature_c: number | null;
  apparent_temperature_c: number | null;
  condition: WeatherCondition;
  precipitation_probability: number | null;
  wind_speed_kmh: number | null;
  is_day: boolean | null;
}

export interface DailyWeather {
  date: string;
  high_c: number | null;
  low_c: number | null;
  condition: WeatherCondition;
  sunrise: string | null;
  sunset: string | null;
  precipitation_probability_max: number | null;
}

export interface WeatherState {
  available: boolean;
  stale: boolean;
  observed_at: string;
  location: WeatherLocation;
  current: CurrentWeather | null;
  today: DailyWeather | null;
  tomorrow: DailyWeather | null;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string | null;
  end: string | null;
  start_date: string | null;
  end_date: string | null;
  all_day: boolean;
  location: string | null;
  calendar_id: string;
  calendar_name: string;
  status: "future" | "ongoing";
}

export interface CalendarState {
  available: boolean;
  stale: boolean;
  observed_at: string;
  events: CalendarEvent[];
  today: CalendarEvent[];
  tomorrow: CalendarEvent[];
  next_event: CalendarEvent | null;
}

export interface OlympusState {
  type: "state";
  mode: ActivityMode;
  active_device: string | null;
  generated_at: string;
  machines: Record<string, MachineState>;
  timezone: string;
  weather: WeatherState | null;
  calendar: CalendarState | null;
  gaming: GamingState | null;
  media: MediaState | null;
  core_host: CoreHostState | null;
  network: NetworkState | null;
  services: Record<string, ServiceState>;
  alerts: ActiveAlert[];
  recoveries: RecoveryNotice[];
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting";
