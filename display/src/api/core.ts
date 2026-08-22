import type {
  ActivityMode,
  ActivityTelemetry,
  MachineState,
  MediaAlbum,
  MediaArtist,
  MediaContext,
  MediaQueueTrack,
  MediaState,
  MediaTrack,
  OlympusState,
  SystemTelemetry,
} from "../types/state";

export const DEFAULT_CORE_WS = "ws://127.0.0.1:8000/ws/display";

export function getCoreWebSocketUrl(): string {
  return import.meta.env.VITE_OLYMPUS_CORE_WS?.trim() || DEFAULT_CORE_WS;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isActivityMode(value: unknown): value is ActivityMode {
  return (
    value === "idle" ||
    value === "development" ||
    value === "gaming" ||
    value === "media" ||
    value === "unknown"
  );
}

function isSystemTelemetry(value: unknown): value is SystemTelemetry {
  if (!isRecord(value)) return false;
  return (
    typeof value.cpu_percent === "number" &&
    typeof value.ram_percent === "number" &&
    typeof value.ram_used_bytes === "number" &&
    typeof value.ram_total_bytes === "number"
  );
}

function isActivityTelemetry(value: unknown): value is ActivityTelemetry {
  if (!isRecord(value)) return false;
  return (
    isActivityMode(value.mode) &&
    (typeof value.application === "string" || value.application === null) &&
    (typeof value.process_name === "string" || value.process_name === null)
  );
}

function isMachineState(value: unknown): value is MachineState {
  if (!isRecord(value)) return false;
  return (
    typeof value.agent_id === "string" &&
    typeof value.hostname === "string" &&
    typeof value.platform === "string" &&
    typeof value.platform_version === "string" &&
    typeof value.online === "boolean" &&
    typeof value.last_seen === "string" &&
    (value.system === null || isSystemTelemetry(value.system)) &&
    (value.activity === null || isActivityTelemetry(value.activity))
  );
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

function isMediaArtist(value: unknown): value is MediaArtist {
  return (
    isRecord(value) &&
    isNullableString(value.id) &&
    typeof value.name === "string"
  );
}

function isMediaAlbum(value: unknown): value is MediaAlbum {
  return (
    isRecord(value) &&
    isNullableString(value.id) &&
    typeof value.name === "string" &&
    isNullableString(value.artwork_url)
  );
}

function isMediaTrack(value: unknown): value is MediaTrack {
  return (
    isRecord(value) &&
    isNullableString(value.id) &&
    typeof value.title === "string" &&
    Array.isArray(value.artists) &&
    value.artists.every(isMediaArtist) &&
    typeof value.duration_ms === "number" &&
    (value.album === null || isMediaAlbum(value.album))
  );
}

function isMediaContext(value: unknown): value is MediaContext {
  return (
    isRecord(value) &&
    typeof value.type === "string" &&
    isNullableString(value.name) &&
    isNullableString(value.uri)
  );
}

function isMediaQueueTrack(value: unknown): value is MediaQueueTrack {
  return (
    isRecord(value) &&
    isNullableString(value.id) &&
    typeof value.title === "string" &&
    Array.isArray(value.artists) &&
    value.artists.every((artist) => typeof artist === "string") &&
    typeof value.duration_ms === "number" &&
    isNullableString(value.artwork_url)
  );
}

function isMediaState(value: unknown): value is MediaState {
  return (
    isRecord(value) &&
    value.provider === "spotify" &&
    typeof value.available === "boolean" &&
    typeof value.is_playing === "boolean" &&
    typeof value.observed_at === "string" &&
    typeof value.progress_ms === "number" &&
    (value.track === null || isMediaTrack(value.track)) &&
    (value.context === null || isMediaContext(value.context)) &&
    Array.isArray(value.queue) &&
    value.queue.length <= 3 &&
    value.queue.every(isMediaQueueTrack)
  );
}

export function parseStateMessage(rawMessage: string): OlympusState | null {
  let value: unknown;
  try {
    value = JSON.parse(rawMessage);
  } catch {
    return null;
  }

  if (
    !isRecord(value) ||
    value.type !== "state" ||
    !isActivityMode(value.mode) ||
    !(typeof value.active_device === "string" || value.active_device === null) ||
    typeof value.generated_at !== "string" ||
    !isRecord(value.machines) ||
    !(
      value.media === undefined ||
      value.media === null ||
      isMediaState(value.media)
    )
  ) {
    return null;
  }

  if (!Object.values(value.machines).every(isMachineState)) return null;
  return {
    ...(value as unknown as OlympusState),
    media: (value.media as MediaState | null | undefined) ?? null,
  };
}
