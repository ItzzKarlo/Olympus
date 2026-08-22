const GIBIBYTE = 1024 ** 3;

export function formatMemory(usedBytes: number, totalBytes: number): string {
  return `${(usedBytes / GIBIBYTE).toFixed(1)} / ${(totalBytes / GIBIBYTE).toFixed(1)} GiB`;
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

export function formatTime(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
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
