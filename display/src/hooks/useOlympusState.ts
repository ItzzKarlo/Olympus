import { useEffect, useState } from "react";

import { getCoreWebSocketUrl, parseDisplayMessage } from "../api/core";
import type { ConnectionStatus, FootballDisplayEvent, GameplayEvent, OlympusState } from "../types/state";

const RECONNECT_DELAY_MS = 2_000;

interface OlympusConnection {
  connectionStatus: ConnectionStatus;
  state: OlympusState | null;
  gameplayEvents: GameplayEvent[];
  footballEvents: FootballDisplayEvent[];
}

export function useOlympusState(): OlympusConnection {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [state, setState] = useState<OlympusState | null>(null);
  const [gameplayEvents, setGameplayEvents] = useState<GameplayEvent[]>([]);
  const [footballEvents, setFootballEvents] = useState<FootballDisplayEvent[]>([]);

  useEffect(() => {
    let active = true;
    let hasConnected = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | null = null;
    const eventTimers = new Set<number>();

    const scheduleReconnect = () => {
      if (!active || retryTimer !== null) return;
      setConnectionStatus(hasConnected ? "reconnecting" : "connecting");
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        openConnection();
      }, RECONNECT_DELAY_MS);
    };

    const openConnection = () => {
      if (!active) return;
      const nextSocket = new WebSocket(getCoreWebSocketUrl());
      socket = nextSocket;

      nextSocket.onopen = () => {
        if (!active || socket !== nextSocket) return;
        hasConnected = true;
        setConnectionStatus("connected");
      };

      nextSocket.onmessage = (event: MessageEvent<string>) => {
        if (!active || socket !== nextSocket) return;
        const message = parseDisplayMessage(event.data);
        if (message === null) return;
        if (message.type === "state") {
          setState(message);
          return;
        }
        if (message.event.category === "football") {
          const footballEvent = message.event;
          setFootballEvents((current) => [...current.filter((item) => item.id !== footballEvent.id), footballEvent]);
          const lifetime = footballEvent.type === "football.goal" ? 6_000
            : footballEvent.type === "football.red_card" ? 3_200
            : footballEvent.type === "football.yellow_card" ? 1_800 : 2_200;
          const eventTimer = window.setTimeout(() => {
            eventTimers.delete(eventTimer);
            if (active) setFootballEvents((current) => current.filter((item) => item.id !== footballEvent.id));
          }, lifetime);
          eventTimers.add(eventTimer);
          return;
        }
        const gameplayEvent = message.event;
        setGameplayEvents((current) => [...current.filter((item) => item.id !== gameplayEvent.id), gameplayEvent]);
        const lifetime = gameplayEvent.type === "minecraft.player.died" ? 2_800
          : gameplayEvent.type === "minecraft.player.healed" ? 520
          : gameplayEvent.type === "minecraft.dimension.changed" ? 900
          : gameplayEvent.type.includes("session.") ? 1_600 : 300;
        const eventTimer = window.setTimeout(() => {
          eventTimers.delete(eventTimer);
          if (active) setGameplayEvents((current) => current.filter((item) => item.id !== gameplayEvent.id));
        }, lifetime);
        eventTimers.add(eventTimer);
      };

      nextSocket.onerror = () => {
        nextSocket.close();
      };

      nextSocket.onclose = () => {
        if (socket === nextSocket) socket = null;
        scheduleReconnect();
      };
    };

    openConnection();

    return () => {
      active = false;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      eventTimers.forEach((timer) => window.clearTimeout(timer));
      socket?.close();
    };
  }, []);

  return { connectionStatus, footballEvents, gameplayEvents, state };
}
