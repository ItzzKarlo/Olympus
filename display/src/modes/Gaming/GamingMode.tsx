import { Brand } from "../../components/Brand";
import { ConnectionStatus } from "../../components/ConnectionStatus";
import type { ConnectionStatus as Status, OlympusState } from "../../types/state";
import { formatBytes, formatLatency, formatMemory, formatSessionDuration } from "../../utils/format";
import { getGamePresentation } from "./gameThemes";
import { MinecraftGamingScene } from "./MinecraftGamingScene";

interface GamingModeProps {
  connectionStatus: Status;
  now: Date;
  state: OlympusState;
}

interface ReadingProps {
  detail?: string;
  label: string;
  value: string;
}

function Reading({ detail, label, value }: ReadingProps) {
  return (
    <div className="gaming-reading">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function GamingMode({ connectionStatus, now, state }: GamingModeProps) {
  const gaming = state.gaming;
  if (!gaming) return null;
  const machine = state.active_device ? state.machines[state.active_device] : undefined;
  if (gaming.game.id === "minecraft" && gaming.minecraft) {
    return <MinecraftGamingScene connectionStatus={connectionStatus} machine={machine} minecraft={gaming.minecraft} now={now} sessionStartedAt={gaming.session_started_at} />;
  }
  const presentation = getGamePresentation(gaming.game.id, gaming.game.name);
  const startedAt = Date.parse(gaming.session_started_at);
  const sessionSeconds = Number.isFinite(startedAt) ? (now.getTime() - startedAt) / 1000 : 0;
  const gpuTemperature = machine?.gpu?.temperature_celsius ?? machine?.temperatures?.gpu_celsius;
  const cpuTemperature = machine?.temperatures?.cpu_celsius;
  const internet = state.network?.internet;
  const showNetwork = internet?.latency_ms != null || internet?.status === "down" || machine?.network;
  const internetReading = internet?.latency_ms != null
    ? `Internet ${formatLatency(internet.latency_ms)}`
    : internet?.status === "down" ? "Internet unavailable" : "Internet reachable";

  return (
    <section className={`scene scene--gaming gaming-motif--${presentation.motif}`} data-game={gaming.game.id}>
      <div className="gaming-atmosphere" aria-hidden="true"><i /><i /><i /></div>
      <header className="scene__header gaming-header">
        <Brand />
        <div className="gaming-header__status">
          <span className="gaming-live"><i aria-hidden="true" /> Gaming / {presentation.label}</span>
          <ConnectionStatus status={connectionStatus} />
        </div>
      </header>

      <div className="gaming-stage">
        <div className="gaming-hero">
          <p className="eyebrow">Olympus gaming session</p>
          <h1>{gaming.game.name}</h1>
          <div className="gaming-device">
            <span className={machine?.online ? "status-pip status-pip--up" : "status-pip status-pip--down"} aria-hidden="true" />
            <strong>{machine?.hostname ?? "Active gaming machine"}</strong>
            {machine?.gpu?.name ? <small>{machine.gpu.name}</small> : null}
          </div>
          {gaming.game.id === "minecraft" ? <p className="gaming-integration-unavailable">Deep integration unavailable</p> : null}
        </div>

        <div className="gaming-session">
          <span>Session</span>
          <time dateTime={gaming.session_started_at}>{formatSessionDuration(sessionSeconds)}</time>
        </div>

        <div className="gaming-performance">
          {gaming.fps != null ? <Reading label="FPS" value={Math.round(gaming.fps).toString()} detail="External frame presentation" /> : null}
          {machine?.gpu && (machine.gpu.utilization_percent != null || gpuTemperature != null) ? <Reading label="GPU" value={machine.gpu.utilization_percent != null ? `${Math.round(machine.gpu.utilization_percent)}%` : `${Math.round(gpuTemperature ?? 0)}°C`} detail={machine.gpu.utilization_percent != null && gpuTemperature != null ? `${Math.round(gpuTemperature)}°C` : machine.gpu.name} /> : null}
          {machine?.gpu?.memory_used_bytes != null && machine.gpu.memory_total_bytes != null ? <Reading label="VRAM" value={formatMemory(machine.gpu.memory_used_bytes, machine.gpu.memory_total_bytes)} /> : null}
          {machine?.system ? <Reading label="CPU" value={`${Math.round(machine.system.cpu_percent)}%`} detail={cpuTemperature != null ? `${Math.round(cpuTemperature)}°C` : undefined} /> : null}
          {machine?.system ? <Reading label="RAM" value={`${Math.round(machine.system.ram_percent)}%`} detail={formatMemory(machine.system.ram_used_bytes, machine.system.ram_total_bytes)} /> : null}
        </div>

        {showNetwork ? (
          <div className="gaming-network">
            <p className="eyebrow">Network</p>
            {internet ? <strong>{internetReading}</strong> : null}
            {machine?.network ? <small>{formatBytes(machine.network.bytes_received)} received · {formatBytes(machine.network.bytes_sent)} sent</small> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
