// ============================================================
// Quotex Alert Intelligence - WebSocket Manager
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { AlertEvent } from "./types";
import {
  MAX_RECONNECT_DELAY_MS,
  INITIAL_RECONNECT_DELAY_MS,
  PING_INTERVAL_MS,
} from "./constants";

export type ConnectionStatus = "connected" | "disconnected" | "connecting" | "error";

export type OnMessageCallback = (event: AlertEvent) => void;
export type OnStatusChangeCallback = (status: ConnectionStatus) => void;

export class WebSocketManager {
  private url: string;
  private ws: WebSocket | null = null;
  private onMessage: OnMessageCallback;
  private onStatusChange: OnStatusChangeCallback;
  private reconnectDelay: number = INITIAL_RECONNECT_DELAY_MS;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;

  constructor(
    url: string,
    onMessage: OnMessageCallback,
    onStatusChange: OnStatusChangeCallback
  ) {
    this.url = url;
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.intentionalClose = false;
    this.onStatusChange("connecting");

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.onStatusChange("error");
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectDelay = INITIAL_RECONNECT_DELAY_MS;
      this.onStatusChange("connected");
      this.startPing();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);

        // Handle pong responses
        if (data.type === "pong") {
          return;
        }

        this.onMessage(data as AlertEvent);
      } catch {
        console.warn("[QAI-WS] Failed to parse message:", event.data);
      }
    };

    this.ws.onclose = () => {
      this.stopPing();
      this.onStatusChange("disconnected");

      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      this.onStatusChange("error");
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.stopPing();

    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close(1000, "Client disconnect");
      }
      this.ws = null;
    }

    this.onStatusChange("disconnected");
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff: 1s -> 2s -> 4s -> 8s -> ... -> 30s max
    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      MAX_RECONNECT_DELAY_MS
    );
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          // If send fails, the onclose handler will trigger reconnect
        }
      }
    }, PING_INTERVAL_MS);
  }

  private stopPing(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }
}
