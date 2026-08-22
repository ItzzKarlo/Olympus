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
