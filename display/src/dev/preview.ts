import type { OlympusState } from "../types/state";

/** Imported only by Vite's development build; never connects to or changes Core. */
export function previewState(): OlympusState | null {
  const query = new URLSearchParams(location.search);
  if (!query.has("preview")) return null;
  const now = new Date();
  const event = { id: "preview", title: "Evening in the garden", start: new Date(+now + 3600000).toISOString(), end: null, start_date: null, end_date: null, all_day: false, location: null, calendar_id: "home", calendar_name: "Home", status: "future" as const };
  const sides = query.get("panels") ?? "none";
  const left = ["left", "both"].includes(sides);
  const right = ["right", "both"].includes(sides);
  const team = { id: "bayern", name: "Bayern Munich", short_name: "Bayern", code: null };
  return {
    type: "state", mode: query.get("preview") === "night" ? "night" : "idle", active_device: null,
    generated_at: now.toISOString(), timezone: "Europe/Berlin", machines: {}, services: {},
    weather: { available: true, stale: false, observed_at: now.toISOString(), location: { latitude: 52, longitude: 13, timezone: "Europe/Berlin", name: "Home" }, current: { temperature_c: 18, apparent_temperature_c: 17, condition: "partly_cloudy", precipitation_probability: 10, wind_speed_kmh: 6, is_day: true }, today: null, tomorrow: null },
    calendar: left ? { available: true, stale: false, observed_at: now.toISOString(), events: [event], today: [], tomorrow: [], next_event: event } : null,
    time_policy: { is_night: query.get("preview") === "night", period_started_at: null, period_ends_at: null, next_transition_at: null },
    football: right ? { available: true, stale: false, observed_at: now.toISOString(), matchday: null, quota: null, tracked_team: team, next_match: { id: "preview", competition: { id: "bl", name: "Bundesliga" }, venue: null, status: "upcoming", clock: null, score: { home: null, away: null }, kickoff: new Date(+now + 86400000).toISOString(), home: team, away: { ...team, id: "dortmund", short_name: "Dortmund" } } } : null,
    news: null, live_events: [], gaming: null, media: null, core_host: null, network: null,
    alerts: query.has("alert") ? [{ id: "preview", incident_key: "preview", type: "network.down", severity: "critical", title: "Connection needs attention", message: "Development preview of a critical incident.", source: "Preview", started_at: now.toISOString(), payload: {} }] : [], recoveries: [],
  };
}
