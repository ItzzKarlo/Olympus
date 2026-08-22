import { Brand } from "./components/Brand";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { useClock } from "./hooks/useClock";
import { useOlympusState } from "./hooks/useOlympusState";
import { DevelopmentMode } from "./modes/Development/DevelopmentMode";
import { IdleMode } from "./modes/Idle/IdleMode";

function StartupScreen() {
  return (
    <main className="startup-screen">
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
  const { connectionStatus, state } = useOlympusState();
  const now = useClock();

  if (state === null) return <StartupScreen />;

  const scene =
    state.mode === "development" ? (
      <DevelopmentMode
        connectionStatus={connectionStatus}
        now={now}
        state={state}
      />
    ) : (
      <IdleMode connectionStatus={connectionStatus} now={now} state={state} />
    );

  return (
    <main className={`olympus-display mode-${state.mode}`}>
      <div key={state.mode} className="scene-transition">
        {scene}
      </div>
      {connectionStatus !== "connected" ? (
        <div className="reconnect-banner" role="status">
          Core unavailable — keeping the last known room state while reconnecting
        </div>
      ) : null}
    </main>
  );
}
