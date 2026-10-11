import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { tokenStore, WS_URL } from "../api/client";
import type { SocketEvent } from "../types";

export type SocketStatus = "connecting" | "open" | "closed";

const MAX_BACKOFF_MS = 15_000;
const HEARTBEAT_MS = 25_000;

/**
 * Keeps one WebSocket open while signed in. Events carry no ticket content: they only tell us
 * which cached queries are stale, and TanStack Query re-fetches them through the authorised REST API.
 */
export function useTicketSocket(enabled: boolean): SocketStatus {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<SocketStatus>("closed");

  useEffect(() => {
    if (!enabled) return;
    let socket: WebSocket | null = null;
    let retry = 0;
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;

    const invalidateFor = (event: SocketEvent) => {
      const id = event.ticket_id;
      const keys: unknown[][] = [
        ["tickets"],
        ["author-dashboard"],
        ["admin-tickets"],
        ["admin-dashboard"],
        ["ticket", id],
        ["messages", id],
        ["admin-ticket", id],
      ];
      keys.forEach((queryKey) => void queryClient.invalidateQueries({ queryKey }));
    };

    const connect = () => {
      const token = tokenStore.get();
      if (!token || stopped) return;
      setStatus("connecting");
      socket = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
      socket.onopen = () => {
        retry = 0;
        setStatus("open");
        heartbeat = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send("ping"), HEARTBEAT_MS);
      };
      socket.onmessage = (message) => {
        if (message.data === "pong") return;
        try {
          invalidateFor(JSON.parse(message.data as string) as SocketEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = (closeEvent) => {
        clearInterval(heartbeat);
        setStatus("closed");
        if (stopped || closeEvent.code === 4401) return; // 4401 = bad/expired token: do not loop
        reconnectTimer = setTimeout(connect, Math.min(1000 * 2 ** retry++, MAX_BACKOFF_MS));
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, [enabled, queryClient]);

  return status;
}
