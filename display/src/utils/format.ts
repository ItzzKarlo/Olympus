const GIBIBYTE = 1024 ** 3;

export function formatMemory(usedBytes: number, totalBytes: number): string {
  return `${(usedBytes / GIBIBYTE).toFixed(1)} / ${(totalBytes / GIBIBYTE).toFixed(1)} GiB`;
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

export function formatPlatform(platform: string): string {
  const names: Record<string, string> = {
    macos: "macOS",
    windows: "Windows",
    linux: "Linux",
  };
  return names[platform.toLowerCase()] ?? platform;
}

export function formatTime(date: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
  }).format(date);
}

export function formatDate(date: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone,
  }).format(date);
}

export function formatTemperature(value: number): string {
  return `${Math.round(value)}°`;
}

export function formatWeatherCondition(condition: string): string {
  return condition.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatEventTime(start: string | null, allDay: boolean, timeZone: string): string {
  if (allDay) return "All day";
  if (!start) return "—";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
  }).format(new Date(start));
}

export function formatRelativeEvent(start: string | null, end: string | null, status: "future" | "ongoing", now: Date): string {
  const target = status === "ongoing" ? end : start;
  if (!target) return status === "ongoing" ? "Happening now" : "Upcoming";
  const minutes = Math.max(0, Math.ceil((new Date(target).getTime() - now.getTime()) / 60_000));
  if (status === "ongoing") {
    if (minutes < 1) return "Ending now";
    return `Now · ends in ${minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`}`;
  }
  if (minutes < 1) return "Starting now";
  if (minutes < 60) return `in ${minutes} min`;
  if (minutes < 24 * 60) return `in ${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  return `in ${Math.ceil(minutes / (24 * 60))} days`;
}

export function formatRelativeNews(publishedAt: string | null, observedAt: string, now: Date): string {
  const timestamp = new Date(publishedAt ?? observedAt).getTime();
  const minutes = Math.max(0, Math.floor((now.getTime() - timestamp) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  return hours > 0
    ? `${hours}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`
    : `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatElapsed(secondsValue: number): string {
  const totalSeconds = Math.max(0, Math.round(secondsValue));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function formatSessionDuration(secondsValue: number): string {
  const totalSeconds = Math.max(0, Math.floor(secondsValue));
  const hours = Math.floor(totalSeconds / 3600).toString().padStart(2, "0");
  const minutes = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

export function formatLatency(latency: number | null): string {
  return latency === null ? "—" : `${latency.toFixed(latency < 10 ? 1 : 0)} ms`;
}
