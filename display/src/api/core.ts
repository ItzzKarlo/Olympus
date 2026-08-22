import type {
  ActivityMode, ActivityTelemetry, ActiveAlert, CalendarEvent, CalendarState, CoreHostState, CurrentWeather, DailyWeather, DisplayEventMessage, FootballDisplayEvent, FootballLineupPlayer, FootballLineups, FootballMatch, FootballMatchEvent, FootballPlayerStatistics, FootballQuotaState, FootballState, FootballStatistics, FootballTeam, FootballTeamLineup, FootballTeamStatistics, GameInfo, GameplayEvent, GamingState, GpuTelemetry,
  LiveEvent, MachineState, MediaAlbum, MediaArtist, MediaContext, MediaQueueTrack,
  MediaState, MediaTrack, NetworkState, NetworkTelemetry, OlympusState,
  NewsArticle, NewsCluster, NewsDisplayEvent, NewsState,
  ProbeState, RecoveryNotice, ServiceState, StorageTelemetry, SystemTelemetry,
  TemperatureTelemetry, TimePolicyState, WeatherCondition, WeatherState,
} from "../types/state";

export const DEFAULT_CORE_WS = "ws://127.0.0.1:8000/ws/display";

export function getCoreWebSocketUrl(): string {
  const override = import.meta.env.VITE_OLYMPUS_CORE_WS?.trim();
  if (override) {
    return override;
  }
  if (typeof window !== "undefined" && window.location.host) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/display`;
  }
  return DEFAULT_CORE_WS;
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
  return ["idle", "development", "gaming", "media", "night", "matchday", "news", "unknown"].includes(value as string);
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

const MATCH_PHASES = ["none", "upcoming", "pre_match", "live", "half_time", "finished", "post_match", "postponed", "cancelled", "suspended", "unknown"];
const FOOTBALL_EVENT_TYPES = ["goal", "own_goal", "penalty_goal", "missed_penalty", "yellow_card", "red_card", "second_yellow", "substitution", "var", "unknown"];

function isFootballTeam(value: unknown): value is FootballTeam {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string" &&
    typeof value.short_name === "string" && isNullableString(value.code);
}

function isFootballScore(value: unknown): boolean {
  return isRecord(value) && isOptionalNumber(value.home) && isOptionalNumber(value.away);
}

function isFootballMatch(value: unknown): value is FootballMatch {
  return isRecord(value) && typeof value.id === "string" && isRecord(value.competition) &&
    typeof value.competition.id === "string" && typeof value.competition.name === "string" &&
    typeof value.kickoff === "string" && (value.venue === null || (isRecord(value.venue) && typeof value.venue.name === "string")) &&
    isFootballTeam(value.home) && isFootballTeam(value.away) && MATCH_PHASES.includes(value.status as string) &&
    (value.clock === null || (isRecord(value.clock) && isOptionalNumber(value.clock.minute) &&
      isOptionalNumber(value.clock.added_time) && typeof value.clock.period === "string")) && isFootballScore(value.score);
}

function isFootballPlayer(value: unknown): boolean {
  return isRecord(value) && isNullableString(value.id) && typeof value.name === "string" &&
    isOptionalNumber(value.number) && isNullableString(value.position);
}

function isFootballMatchEvent(value: unknown): value is FootballMatchEvent {
  return isRecord(value) && typeof value.id === "string" && FOOTBALL_EVENT_TYPES.includes(value.type as string) &&
    isOptionalNumber(value.minute) && isOptionalNumber(value.added_time) &&
    (value.team === null || isFootballTeam(value.team)) && (value.player === null || isFootballPlayer(value.player)) &&
    (value.assist === null || isFootballPlayer(value.assist)) && (value.score_after === null || isFootballScore(value.score_after)) &&
    typeof value.for_tracked_team === "boolean" && isNullableString(value.detail) &&
    (value.location === null || (isRecord(value.location) && isOptionalNumber(value.location.x) && isOptionalNumber(value.location.y)));
}

function isFootballLineupPlayer(value: unknown): value is FootballLineupPlayer {
  return isFootballPlayer(value) && isRecord(value) && isOptionalNumber(value.number) &&
    isNullableString(value.position) && typeof value.starter === "boolean";
}

function isFootballTeamLineup(value: unknown): value is FootballTeamLineup {
  return isRecord(value) && isFootballTeam(value.team) && isNullableString(value.formation) &&
    Array.isArray(value.players) && value.players.every(isFootballLineupPlayer);
}

function isFootballLineups(value: unknown): value is FootballLineups {
  return isRecord(value) && (value.home === null || isFootballTeamLineup(value.home)) &&
    (value.away === null || isFootballTeamLineup(value.away));
}

function isFootballTeamStatistics(value: unknown): value is FootballTeamStatistics {
  if (!isRecord(value)) return false;
  return ["possession_percent", "shots", "shots_on_target", "corners", "fouls", "yellow_cards", "red_cards", "offsides", "passes", "pass_accuracy_percent"]
    .every((field) => isOptionalNumber(value[field]));
}

function isFootballStatistics(value: unknown): value is FootballStatistics {
  return isRecord(value) && (value.home === null || isFootballTeamStatistics(value.home)) &&
    (value.away === null || isFootballTeamStatistics(value.away));
}

function hasOptionalNumbers(value: unknown, fields: string[]): value is Record<string, number | null> {
  return isRecord(value) && fields.every((field) => isOptionalNumber(value[field]));
}

function isFootballPlayerStatistics(value: unknown): value is FootballPlayerStatistics {
  return isRecord(value) && isFootballPlayer(value.player) && isFootballTeam(value.team) &&
    typeof value.for_tracked_team === "boolean" && isOptionalNumber(value.minutes) &&
    isOptionalNumber(value.rating) && (value.starter === null || typeof value.starter === "boolean") &&
    isOptionalNumber(value.goals) && isOptionalNumber(value.assists) &&
    hasOptionalNumbers(value.shots, ["total", "on_target"]) &&
    hasOptionalNumbers(value.passes, ["total", "key", "accuracy_percent"]) &&
    hasOptionalNumbers(value.defending, ["tackles", "interceptions", "blocks"]) &&
    hasOptionalNumbers(value.duels, ["total", "won"]) &&
    hasOptionalNumbers(value.dribbles, ["attempted", "successful"]) &&
    hasOptionalNumbers(value.fouls, ["committed", "drawn"]) &&
    hasOptionalNumbers(value.cards, ["yellow", "red"]) &&
    hasOptionalNumbers(value.penalties, ["won", "committed", "scored", "missed", "saved"]);
}

function isFootballQuota(value: unknown): value is FootballQuotaState {
  return isRecord(value) && ["daily_limit", "daily_remaining", "minute_limit", "minute_remaining"]
    .every((field) => isOptionalNumber(value[field])) && typeof value.low === "boolean" &&
    typeof value.critical === "boolean" && typeof value.observed_at === "string";
}

function isFootballState(value: unknown): value is FootballState {
  if (!isRecord(value) || typeof value.available !== "boolean" || typeof value.stale !== "boolean" ||
    typeof value.observed_at !== "string" || !isFootballTeam(value.tracked_team) ||
    !(value.next_match === null || isFootballMatch(value.next_match)) ||
    !(value.quota === null || isFootballQuota(value.quota))) return false;
  if (value.matchday === null) return true;
  const context = value.matchday;
  return isRecord(context) && typeof context.active === "boolean" && MATCH_PHASES.includes(context.phase as string) &&
    isFootballTeam(context.tracked_team) && isFootballMatch(context.match) && Array.isArray(context.events) &&
    context.events.every(isFootballMatchEvent) && (context.lineups === null || isFootballLineups(context.lineups)) &&
    (context.statistics === null || isFootballStatistics(context.statistics)) && Array.isArray(context.statistics_history) &&
    context.statistics_history.every((item) => isRecord(item) && isOptionalNumber(item.minute) &&
      (item.home === null || isFootballTeamStatistics(item.home)) && (item.away === null || isFootballTeamStatistics(item.away)) &&
      typeof item.observed_at === "string") && Array.isArray(context.player_statistics) &&
    context.player_statistics.every(isFootballPlayerStatistics) && Array.isArray(context.watched_players) &&
    context.watched_players.every((item) => isRecord(item) && isFootballPlayer(item.player) &&
      ["starting", "playing", "substituted", "bench", "unavailable", "finished"].includes(item.status as string) &&
      isOptionalNumber(item.rating) && isOptionalNumber(item.previous_rating) && isOptionalNumber(item.rating_delta) &&
      (item.statistics === null || isFootballPlayerStatistics(item.statistics))) &&
    Array.isArray(context.top_tracked_players) && context.top_tracked_players.every(isFootballPlayerStatistics) &&
    Array.isArray(context.top_opponent_players) && context.top_opponent_players.every(isFootballPlayerStatistics) &&
    Array.isArray(context.rating_history) && context.rating_history.every((history) => isRecord(history) &&
      isFootballPlayer(history.player) && Array.isArray(history.samples) && history.samples.every((sample) =>
        isRecord(sample) && isOptionalNumber(sample.minute) && typeof sample.rating === "number" && typeof sample.observed_at === "string")) &&
    Array.isArray(context.match_flow) && context.match_flow.every((point) => isRecord(point) &&
      isOptionalNumber(point.minute) && typeof point.tracked_team === "number" && typeof point.opponent === "number" &&
      ["statistics", "events", "combined"].includes(point.basis as string) && typeof point.observed_at === "string") &&
    ["win", "draw", "loss", "unknown"].includes(context.result as string) && typeof context.stale === "boolean" &&
    typeof context.observed_at === "string";
}

function isFootballDisplayEvent(value: unknown): value is FootballDisplayEvent {
  return isRecord(value) && typeof value.id === "string" && typeof value.type === "string" &&
    value.category === "football" && ["info", "warning", "critical"].includes(value.severity as string) &&
    typeof value.timestamp === "string" && typeof value.source === "string" && isRecord(value.payload) &&
    (value.payload.event === undefined || isFootballMatchEvent(value.payload.event));
}

const NEWS_TOPICS = ["world", "germany", "local", "politics", "economy", "technology", "science", "weather", "transport", "sports", "entertainment", "other"];
const NEWS_LEVELS = ["ambient", "notable", "important", "major"];

function isNewsSource(value: unknown): boolean {
  return isRecord(value) && typeof value.id === "string" && typeof value.name === "string" &&
    typeof value.language === "string" && isNullableString(value.region) && typeof value.trust === "number";
}

function isNewsArticle(value: unknown): value is NewsArticle {
  return isRecord(value) && typeof value.id === "string" && isNullableString(value.provider_id) &&
    typeof value.headline === "string" && isNewsSource(value.source) && typeof value.url === "string" &&
    typeof value.canonical_url === "string" && isNullableString(value.published_at) &&
    typeof value.observed_at === "string" && isNullableString(value.summary) && typeof value.language === "string" &&
    Array.isArray(value.categories) && value.categories.every((item) => typeof item === "string") &&
    NEWS_TOPICS.includes(value.topic as string);
}

function isNewsCluster(value: unknown): value is NewsCluster {
  return isRecord(value) && typeof value.id === "string" && typeof value.headline === "string" &&
    isNullableString(value.summary) && typeof value.language === "string" && NEWS_TOPICS.includes(value.topic as string) &&
    Array.isArray(value.articles) && value.articles.every(isNewsArticle) &&
    Array.isArray(value.sources) && value.sources.every(isNewsSource) &&
    typeof value.first_seen_at === "string" && typeof value.latest_seen_at === "string" &&
    isRecord(value.importance) && typeof value.importance.score === "number" &&
    NEWS_LEVELS.includes(value.importance.level as string) && isRecord(value.importance.factors) &&
    Object.values(value.importance.factors).every((item) => typeof item === "number");
}

function isNewsState(value: unknown): value is NewsState {
  return isRecord(value) && typeof value.available === "boolean" && isNullableString(value.last_updated_at) &&
    typeof value.stale === "boolean" && Array.isArray(value.top_stories) && value.top_stories.every(isNewsCluster) &&
    Array.isArray(value.ambient) && value.ambient.every(isNewsCluster) &&
    (value.active_story === null || isNewsCluster(value.active_story)) &&
    (value.presentation === null || (isRecord(value.presentation) && typeof value.presentation.active === "boolean" &&
      typeof value.presentation.story_id === "string" && NEWS_LEVELS.includes(value.presentation.level as string) &&
      typeof value.presentation.started_at === "string" && typeof value.presentation.ends_at === "string")) &&
    Array.isArray(value.feed_health) && value.feed_health.every((health) => isRecord(health) &&
      typeof health.feed_id === "string" && isNullableString(health.last_success_at) &&
      isNullableString(health.last_error) && typeof health.stale === "boolean");
}

function isNewsDisplayEvent(value: unknown): value is NewsDisplayEvent {
  return isRecord(value) && typeof value.id === "string" && typeof value.type === "string" &&
    value.category === "news" && ["info", "warning", "critical"].includes(value.severity as string) &&
    typeof value.timestamp === "string" && typeof value.source === "string" && isRecord(value.payload) &&
    (value.payload.story === undefined || isNewsCluster(value.payload.story));
}

function isLiveEvent(value: unknown): value is LiveEvent {
  return isRecord(value) && typeof value.id === "string" && typeof value.type === "string" &&
    typeof value.title === "string" && typeof value.status === "string" && isNullableString(value.started_at) &&
    typeof value.updated_at === "string" && typeof value.provider === "string" &&
    isNullableString(value.summary) && isRecord(value.data);
}

const WEATHER_CONDITIONS: WeatherCondition[] = [
  "clear", "mostly_clear", "partly_cloudy", "cloudy", "fog", "drizzle",
  "rain", "heavy_rain", "snow", "thunderstorm", "unknown",
];

function isCurrentWeather(value: unknown): value is CurrentWeather {
  return isRecord(value) && isOptionalNumber(value.temperature_c) &&
    isOptionalNumber(value.apparent_temperature_c) &&
    WEATHER_CONDITIONS.includes(value.condition as WeatherCondition) &&
    isOptionalNumber(value.precipitation_probability) && isOptionalNumber(value.wind_speed_kmh) &&
    (value.is_day === null || typeof value.is_day === "boolean");
}

function isDailyWeather(value: unknown): value is DailyWeather {
  return isRecord(value) && typeof value.date === "string" &&
    isOptionalNumber(value.high_c) && isOptionalNumber(value.low_c) &&
    WEATHER_CONDITIONS.includes(value.condition as WeatherCondition) &&
    isNullableString(value.sunrise) && isNullableString(value.sunset) &&
    isOptionalNumber(value.precipitation_probability_max);
}

function isWeatherState(value: unknown): value is WeatherState {
  return isRecord(value) && typeof value.available === "boolean" && typeof value.stale === "boolean" &&
    typeof value.observed_at === "string" && isRecord(value.location) &&
    typeof value.location.latitude === "number" && typeof value.location.longitude === "number" &&
    typeof value.location.timezone === "string" && isNullableString(value.location.name) &&
    (value.current === null || isCurrentWeather(value.current)) &&
    (value.today === null || isDailyWeather(value.today)) &&
    (value.tomorrow === null || isDailyWeather(value.tomorrow));
}

function isCalendarEvent(value: unknown): value is CalendarEvent {
  return isRecord(value) && typeof value.id === "string" && typeof value.title === "string" &&
    isNullableString(value.start) && isNullableString(value.end) &&
    isNullableString(value.start_date) && isNullableString(value.end_date) &&
    typeof value.all_day === "boolean" && isNullableString(value.location) &&
    typeof value.calendar_id === "string" && typeof value.calendar_name === "string" &&
    (value.status === "future" || value.status === "ongoing");
}

function isCalendarState(value: unknown): value is CalendarState {
  return isRecord(value) && typeof value.available === "boolean" && typeof value.stale === "boolean" &&
    typeof value.observed_at === "string" && Array.isArray(value.events) && value.events.every(isCalendarEvent) &&
    Array.isArray(value.today) && value.today.every(isCalendarEvent) &&
    Array.isArray(value.tomorrow) && value.tomorrow.every(isCalendarEvent) &&
    (value.next_event === null || isCalendarEvent(value.next_event));
}

function isTimePolicyState(value: unknown): value is TimePolicyState {
  return isRecord(value) && typeof value.is_night === "boolean" &&
    isNullableString(value.period_started_at) && isNullableString(value.period_ends_at) &&
    isNullableString(value.next_transition_at);
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
    !(value.timezone === undefined || typeof value.timezone === "string") ||
    !(value.weather === undefined || value.weather === null || isWeatherState(value.weather)) ||
    !(value.calendar === undefined || value.calendar === null || isCalendarState(value.calendar)) ||
    !(value.football === undefined || value.football === null || isFootballState(value.football)) ||
    !(value.news === undefined || value.news === null || isNewsState(value.news)) ||
    !(value.live_events === undefined || (Array.isArray(value.live_events) && value.live_events.every(isLiveEvent))) ||
    !(value.time_policy === undefined || isTimePolicyState(value.time_policy)) ||
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
    timezone: (value.timezone as string | undefined) ?? "Europe/Berlin",
    weather: (value.weather as WeatherState | null | undefined) ?? null,
    calendar: (value.calendar as CalendarState | null | undefined) ?? null,
    football: (value.football as FootballState | null | undefined) ?? null,
    news: (value.news as NewsState | null | undefined) ?? null,
    live_events: (value.live_events as LiveEvent[] | undefined) ?? [],
    time_policy: (value.time_policy as TimePolicyState | undefined) ?? {
      is_night: false,
      period_started_at: null,
      period_ends_at: null,
      next_transition_at: null,
    },
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
  if (isRecord(value) && value.type === "event" && (isGameplayEvent(value.event) || isFootballDisplayEvent(value.event) || isNewsDisplayEvent(value.event))) {
    return value as unknown as DisplayEventMessage;
  }
  return parseStateMessage(rawMessage);
}
