import { Brand } from "./components/Brand";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { EventOverlayLayer } from "./components/EventOverlayLayer";
import { GameplayEventLayer } from "./components/GameplayEventLayer";
import { ParticleField } from "./components/ParticleField";
import { useClock } from "./hooks/useClock";
import { useOlympusState } from "./hooks/useOlympusState";
import { useSceneTheme } from "./hooks/useSceneTheme";
import { DevelopmentMode } from "./modes/Development/DevelopmentMode";
import { IdleMode } from "./modes/Idle/IdleMode";
import { GamingMode } from "./modes/Gaming/GamingMode";
import { MediaMode } from "./modes/Media/MediaMode";
import { sceneStyle } from "./theme/SceneTheme";
import { idleTheme } from "./theme/themes";

function StartupScreen() {
  return (
    <main className="startup-screen">
      <ParticleField theme={idleTheme.particles} />
      <Brand />
      <div className="startup-screen__message">
        <span className="startup-screen__orbit" aria-hidden="true" />
        <p className="eyebrow">Local room system</p>
        <h1>Connecting to Core</h1>
        <p>Waiting for Olympus to describe the room.</p>
      </div>
      <ConnectionStatus status="connecting" />
    </main>
  );
}

export default function App() {
  const { connectionStatus, gameplayEvents, state } = useOlympusState();
  const now = useClock();
  const theme = useSceneTheme(connectionStatus === "connected" ? state : null);

  if (state === null) return <StartupScreen />;

  const scene = state.mode === "gaming" && state.gaming ? (
      <GamingMode connectionStatus={connectionStatus} now={now} state={state} />
    ) : state.mode === "development" ? (
      <DevelopmentMode
        connectionStatus={connectionStatus}
        now={now}
        state={state}
      />
    ) : state.mode === "media" && state.media?.track ? (
      <MediaMode connectionStatus={connectionStatus} media={state.media} />
    ) : (
      <IdleMode connectionStatus={connectionStatus} now={now} state={state} />
    );

  return (
    <main className={`olympus-display mode-${state.mode}`} style={sceneStyle(theme)}>
      <ParticleField
        key={`${state.mode}:${state.gaming?.game.id ?? ""}:${state.weather?.current?.condition ?? ""}`}
        theme={theme.particles}
      />
      <div key={state.mode} className="scene-transition">
        {scene}
      </div>
      <GameplayEventLayer events={gameplayEvents} />
      <EventOverlayLayer alerts={state.alerts} now={now} recoveries={state.recoveries} />
      {connectionStatus !== "connected" ? (
        <div className="reconnect-banner" role="status">
          Core unavailable — keeping the last known room state while reconnecting
        </div>
      ) : null}
    </main>
  );
}
