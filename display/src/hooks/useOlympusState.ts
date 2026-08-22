import { useEffect, useState } from "react";

import { getCoreWebSocketUrl, parseStateMessage } from "../api/core";
import type { ConnectionStatus, OlympusState } from "../types/state";

const RECONNECT_DELAY_MS = 2_000;

interface OlympusConnection {
  connectionStatus: ConnectionStatus;
  state: OlympusState | null;
}

export function useOlympusState(): OlympusConnection {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [state, setState] = useState<OlympusState | null>(null);

  useEffect(() => {
    let active = true;
    let hasConnected = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | null = null;

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
        const nextState = parseStateMessage(event.data);
        if (nextState !== null) setState(nextState);
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
      socket?.close();
    };
  }, []);

  return { connectionStatus, state };
}
