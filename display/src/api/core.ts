import type {
  ActivityMode, ActivityTelemetry, ActiveAlert, CoreHostState, DisplayEventMessage, GameInfo, GameplayEvent, GamingState, GpuTelemetry,
  MachineState, MediaAlbum, MediaArtist, MediaContext, MediaQueueTrack,
  MediaState, MediaTrack, NetworkState, NetworkTelemetry, OlympusState,
  ProbeState, RecoveryNotice, ServiceState, StorageTelemetry, SystemTelemetry,
  TemperatureTelemetry,
} from "../types/state";

export const DEFAULT_CORE_WS = "ws://127.0.0.1:8000/ws/display";

export function getCoreWebSocketUrl(): string {
  return import.meta.env.VITE_OLYMPUS_CORE_WS?.trim() || DEFAULT_CORE_WS;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

function isOptionalNumber(value: unknown): value is number | null | undefined {
  return value === undefined || value === null || typeof value === "number";
}

function isActivityMode(value: unknown): value is ActivityMode {
  return ["idle", "development", "gaming", "media", "unknown"].includes(value as string);
}

function isSystemTelemetry(value: unknown): value is SystemTelemetry {
  return isRecord(value) && typeof value.cpu_percent === "number" &&
    typeof value.ram_percent === "number" && typeof value.ram_used_bytes === "number" &&
    typeof value.ram_total_bytes === "number" && isOptionalNumber(value.uptime_seconds);
}

function isStorageTelemetry(value: unknown): value is StorageTelemetry {
  return isRecord(value) && typeof value.root_used_percent === "number" &&
    typeof value.root_free_bytes === "number" && typeof value.root_total_bytes === "number";
}

function isNetworkTelemetry(value: unknown): value is NetworkTelemetry {
  return isRecord(value) && typeof value.bytes_sent === "number" &&
    typeof value.bytes_received === "number";
}

function isTemperatureTelemetry(value: unknown): value is TemperatureTelemetry {
  return isRecord(value) && isOptionalNumber(value.cpu_celsius) &&
    isOptionalNumber(value.gpu_celsius);
}

function isGpuTelemetry(value: unknown): value is GpuTelemetry {
  return isRecord(value) && typeof value.name === "string" &&
    isOptionalNumber(value.utilization_percent) && isOptionalNumber(value.memory_used_bytes) &&
    isOptionalNumber(value.memory_total_bytes) && isOptionalNumber(value.temperature_celsius);
}

function isGameInfo(value: unknown): value is GameInfo {
  return isRecord(value) && typeof value.id === "string" && value.id.length > 0 &&
    typeof value.name === "string" && value.name.length > 0;
}

function isActivityTelemetry(value: unknown): value is ActivityTelemetry {
  return isRecord(value) && isActivityMode(value.mode) &&
    isNullableString(value.application) && isNullableString(value.process_name) &&
    (value.game === undefined || value.game === null || isGameInfo(value.game)) &&
    isOptionalNumber(value.fps);
}

function isMachineState(value: unknown): value is MachineState {
  return isRecord(value) && typeof value.agent_id === "string" &&
    typeof value.hostname === "string" && typeof value.platform === "string" &&
    typeof value.platform_version === "string" && typeof value.online === "boolean" &&
    typeof value.last_seen === "string" &&
    (value.system === null || isSystemTelemetry(value.system)) &&
    (value.storage === undefined || value.storage === null || isStorageTelemetry(value.storage)) &&
    (value.network === undefined || value.network === null || isNetworkTelemetry(value.network)) &&
    (value.temperatures === undefined || value.temperatures === null || isTemperatureTelemetry(value.temperatures)) &&
    (value.gpu === undefined || value.gpu === null || isGpuTelemetry(value.gpu)) &&
    (value.activity === null || isActivityTelemetry(value.activity));
}

function isMediaArtist(value: unknown): value is MediaArtist {
  return isRecord(value) && isNullableString(value.id) && typeof value.name === "string";
}

function isMediaAlbum(value: unknown): value is MediaAlbum {
  return isRecord(value) && isNullableString(value.id) && typeof value.name === "string" &&
    isNullableString(value.artwork_url);
}

function isMediaTrack(value: unknown): value is MediaTrack {
  return isRecord(value) && isNullableString(value.id) && typeof value.title === "string" &&
    Array.isArray(value.artists) && value.artists.every(isMediaArtist) &&
    typeof value.duration_ms === "number" && (value.album === null || isMediaAlbum(value.album));
}

function isMediaContext(value: unknown): value is MediaContext {
  return isRecord(value) && typeof value.type === "string" &&
    isNullableString(value.name) && isNullableString(value.uri);
}

function isMediaQueueTrack(value: unknown): value is MediaQueueTrack {
  return isRecord(value) && isNullableString(value.id) && typeof value.title === "string" &&
    Array.isArray(value.artists) && value.artists.every((artist) => typeof artist === "string") &&
    typeof value.duration_ms === "number" && isNullableString(value.artwork_url);
}

function isMediaState(value: unknown): value is MediaState {
  return isRecord(value) && value.provider === "spotify" && typeof value.available === "boolean" &&
    typeof value.is_playing === "boolean" && typeof value.observed_at === "string" &&
    typeof value.progress_ms === "number" && (value.track === null || isMediaTrack(value.track)) &&
    (value.context === null || isMediaContext(value.context)) && Array.isArray(value.queue) &&
    value.queue.length <= 3 && value.queue.every(isMediaQueueTrack);
}

function isProbeState(value: unknown): value is ProbeState {
  return isRecord(value) &&
    (value.status === "up" || value.status === "down" || value.status === "unknown") &&
    isOptionalNumber(value.latency_ms) &&
    (value.last_checked === null || typeof value.last_checked === "string");
}

function isNetworkState(value: unknown): value is NetworkState {
  return isRecord(value) && isProbeState(value.gateway) && isRecord(value.gateway) &&
    (value.gateway.host === undefined || isNullableString(value.gateway.host)) &&
    (value.gateway.source === undefined || typeof value.gateway.source === "string") && isProbeState(value.dns) &&
    isProbeState(value.internet) && isProbeState(value.https) && isRecord(value.targets) &&
    Object.values(value.targets).every((target) => isProbeState(target) && isRecord(target) &&
      typeof target.id === "string" && typeof target.name === "string");
}

function isGamingState(value: unknown): value is GamingState {
  return isRecord(value) && isGameInfo(value.game) &&
    typeof value.session_started_at === "string" && isOptionalNumber(value.fps) &&
    (value.integration === undefined || value.integration === null || isGamingIntegration(value.integration)) &&
    (value.minecraft === undefined || value.minecraft === null || isMinecraftState(value.minecraft));
}

function isGamingIntegration(value: unknown): boolean {
  return isRecord(value) && typeof value.type === "string" &&
    typeof value.available === "boolean" && typeof value.connected === "boolean" &&
    typeof value.last_seen === "string" && isRecord(value.observer) &&
    typeof value.observer.id === "string" && typeof value.observer.name === "string" &&
    typeof value.observer.version === "string";
}

function isMinecraftState(value: unknown): boolean {
  if (!isRecord(value) || !isRecord(value.connection) || !isRecord(value.world) ||
    !isRecord(value.player) || !isRecord(value.player.position)) return false;
  const player = value.player;
  const connectionType = value.connection.type;
  const gameMode = player.game_mode;
  return (connectionType === "singleplayer" || connectionType === "multiplayer") &&
    isNullableString(value.connection.server_name) && isNullableString(value.connection.server_address) &&
    isNullableString(value.connection.world_name) && typeof value.world.dimension === "string" &&
    typeof value.world.biome === "string" && ["x", "y", "z"].every((axis) =>
      isOptionalNumber((player.position as Record<string, unknown>)[axis])) &&
    ["health", "max_health", "food", "max_food", "armor"].every((field) =>
      isOptionalNumber(player[field])) &&
    (player.experience === null || (isRecord(player.experience) &&
      isOptionalNumber(player.experience.level) && isOptionalNumber(player.experience.progress))) &&
    ["survival", "creative", "adventure", "spectator", "unknown"].includes(gameMode as string) &&
    typeof value.observed_at === "string" && typeof value.low_health === "boolean";
}

function isGameplayEvent(value: unknown): value is GameplayEvent {
  return isRecord(value) && typeof value.id === "string" && typeof value.type === "string" &&
    value.category === "gameplay" && ["info", "warning", "critical"].includes(value.severity as string) &&
    typeof value.timestamp === "string" && isRecord(value.source) &&
    typeof value.source.agent_id === "string" && typeof value.source.integration === "string" &&
    isRecord(value.payload);
}

function isServiceState(value: unknown): value is ServiceState {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string" &&
    isProbeState(value) && (value.last_changed === null || typeof value.last_changed === "string");
}

function isCoreHostState(value: unknown): value is CoreHostState {
  return isRecord(value) && typeof value.hostname === "string" && typeof value.platform === "string" &&
    typeof value.observed_at === "string" && isSystemTelemetry(value.system) &&
    isStorageTelemetry(value.storage);
}

function isActiveAlert(value: unknown): value is ActiveAlert {
  return isRecord(value) && typeof value.id === "string" && typeof value.incident_key === "string" &&
    typeof value.type === "string" && ["info", "warning", "critical"].includes(value.severity as string) &&
    typeof value.title === "string" && typeof value.message === "string" &&
    typeof value.source === "string" && typeof value.started_at === "string" && isRecord(value.payload);
}

function isRecoveryNotice(value: unknown): value is RecoveryNotice {
  return isRecord(value) && typeof value.id === "string" && typeof value.incident_key === "string" &&
    typeof value.type === "string" && typeof value.title === "string" && typeof value.message === "string" &&
    typeof value.source === "string" && typeof value.recovered_at === "string" &&
    typeof value.downtime_seconds === "number" && typeof value.expires_at === "string" &&
    isRecord(value.payload);
}

function normalizeMachine(machine: MachineState): MachineState {
  return {
    ...machine,
    system: machine.system ? { ...machine.system, uptime_seconds: machine.system.uptime_seconds ?? null } : null,
    storage: machine.storage ?? null,
    network: machine.network ?? null,
    temperatures: machine.temperatures ?? null,
    gpu: machine.gpu ?? null,
    activity: machine.activity ? {
      ...machine.activity,
      game: machine.activity.game ?? null,
      fps: machine.activity.fps ?? null,
    } : null,
  };
}

export function parseStateMessage(rawMessage: string): OlympusState | null {
  let value: unknown;
  try { value = JSON.parse(rawMessage); } catch { return null; }
  if (!isRecord(value) || value.type !== "state" || !isActivityMode(value.mode) ||
    !(typeof value.active_device === "string" || value.active_device === null) ||
    typeof value.generated_at !== "string" || !isRecord(value.machines) ||
    !Object.values(value.machines).every(isMachineState) ||
    !(value.gaming === undefined || value.gaming === null || isGamingState(value.gaming)) ||
    !(value.media === undefined || value.media === null || isMediaState(value.media)) ||
    !(value.core_host === undefined || value.core_host === null || isCoreHostState(value.core_host)) ||
    !(value.network === undefined || value.network === null || isNetworkState(value.network)) ||
    !(value.services === undefined || (isRecord(value.services) && Object.values(value.services).every(isServiceState))) ||
    !(value.alerts === undefined || (Array.isArray(value.alerts) && value.alerts.every(isActiveAlert))) ||
    !(value.recoveries === undefined || (Array.isArray(value.recoveries) && value.recoveries.every(isRecoveryNotice)))) {
    return null;
  }
  return {
    ...(value as unknown as OlympusState),
    machines: Object.fromEntries(Object.entries(value.machines).map(([id, machine]) =>
      [id, normalizeMachine(machine as unknown as MachineState)])),
    media: (value.media as MediaState | null | undefined) ?? null,
    gaming: value.gaming ? {
      ...(value.gaming as unknown as GamingState),
      integration: (value.gaming.integration as GamingState["integration"] | undefined) ?? null,
      minecraft: (value.gaming.minecraft as GamingState["minecraft"] | undefined) ?? null,
    } : null,
    core_host: (value.core_host as CoreHostState | null | undefined) ?? null,
    network: (value.network as NetworkState | null | undefined) ?? null,
    services: (value.services as Record<string, ServiceState> | undefined) ?? {},
    alerts: (value.alerts as ActiveAlert[] | undefined) ?? [],
    recoveries: (value.recoveries as RecoveryNotice[] | undefined) ?? [],
  };
}

export function parseDisplayMessage(rawMessage: string): OlympusState | DisplayEventMessage | null {
  let value: unknown;
  try { value = JSON.parse(rawMessage); } catch { return null; }
  if (isRecord(value) && value.type === "event" && isGameplayEvent(value.event)) {
    return value as unknown as DisplayEventMessage;
  }
  return parseStateMessage(rawMessage);
}
