import { Brand } from "./components/Brand";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { EventOverlayLayer } from "./components/EventOverlayLayer";
import { FootballEventLayer } from "./components/FootballEventLayer";
import { GameplayEventLayer } from "./components/GameplayEventLayer";
import { HermesHealthBar } from "./components/HermesHealthBar";
import { ParticleField } from "./components/ParticleField";
import { SeasonalEnvironment } from "./components/SeasonalEnvironment";
import { SeasonalLayer } from "./components/SeasonalLayer";
import { useClock } from "./hooks/useClock";
import { useOlympusState } from "./hooks/useOlympusState";
import { useSceneTheme } from "./hooks/useSceneTheme";
import { DevelopmentMode } from "./modes/Development/DevelopmentMode";
import { IdleMode } from "./modes/Idle/IdleMode";
import { GamingMode } from "./modes/Gaming/GamingMode";
import { MediaMode } from "./modes/Media/MediaMode";
import { MatchdayMode } from "./modes/Matchday/MatchdayMode";
import { NightMode } from "./modes/Night/NightMode";
import { NewsMode } from "./modes/News/NewsMode";
import { sceneStyle } from "./theme/SceneTheme";
import { getSeasonalPresentation } from "./theme/seasonalTheme";
import { idleTheme } from "./theme/themes";

function seasonalDateFor(now: Date): Date {
  const raw = new URLSearchParams(window.location.search).get("seasonal_date");
  if (!raw) return now;

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (!match) return now;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const candidate = new Date(now);
  candidate.setFullYear(year, month - 1, day);

  if (
    candidate.getFullYear() !== year ||
    candidate.getMonth() !== month - 1 ||
    candidate.getDate() !== day
  ) {
    return now;
  }

  return candidate;
}

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
  const { connectionStatus, footballEvents, gameplayEvents, state } = useOlympusState();
  const now = useClock();
  const seasonal = getSeasonalPresentation(seasonalDateFor(now));
  const theme = useSceneTheme(connectionStatus === "connected" ? state : null, seasonal);

  if (state === null) return <StartupScreen />;

  const scene = state.mode === "matchday" && state.football?.matchday ? (
      <MatchdayMode connectionStatus={connectionStatus} now={now} state={state} />
    ) : state.mode === "news" && state.news?.active_story ? (
      <NewsMode connectionStatus={connectionStatus} now={now} state={state} />
    ) : state.mode === "gaming" && state.gaming ? (
      <GamingMode connectionStatus={connectionStatus} now={now} state={state} />
    ) : state.mode === "development" ? (
      <DevelopmentMode
        connectionStatus={connectionStatus}
        now={now}
        state={state}
      />
    ) : state.mode === "media" && state.media?.track ? (
      <MediaMode connectionStatus={connectionStatus} media={state.media} />
    ) : state.mode === "night" ? (
      <NightMode connectionStatus={connectionStatus} now={now} state={state} />
    ) : (
      <IdleMode connectionStatus={connectionStatus} now={now} state={state} />
    );

  return (
    <main
      className={`olympus-display mode-${state.mode} seasonal-${seasonal.id}${state.time_policy.is_night ? " policy-night" : ""}`}
      data-season={seasonal.season}
      data-seasonal-event={seasonal.event ?? undefined}
      style={sceneStyle(theme)}
    >
      <SeasonalLayer presentation={seasonal} />
      <SeasonalEnvironment mode={state.mode} presentation={seasonal} night={state.time_policy.is_night} retreat={state.alerts.length > 0} />
      <div key={state.mode} className="scene-transition">
        {scene}
      </div>
      <GameplayEventLayer events={state.mode === "gaming" ? gameplayEvents : []} />
      <FootballEventLayer events={footballEvents} state={state} />
      <EventOverlayLayer alerts={state.alerts} now={now} recoveries={state.recoveries} />
      <HermesHealthBar connectionStatus={connectionStatus} state={state} />
      {connectionStatus !== "connected" ? (
        <div className="reconnect-banner" role="status">
          Core unavailable — keeping the last known room state while reconnecting
        </div>
      ) : null}
    </main>
  );
}
