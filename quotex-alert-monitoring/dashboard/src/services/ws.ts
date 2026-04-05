export type WsStatus = 'connected' | 'connecting' | 'disconnected';

export interface WsMessage {
  event: string;
  data: unknown;
}

interface WsConnection {
  socket: WebSocket | null;
  close: () => void;
}

export function connectWs(
  url: string,
  onMessage: (msg: WsMessage) => void,
  onStatusChange: (status: WsStatus) => void
): WsConnection {
  let socket: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const maxReconnectDelay = 30000;
  const baseDelay = 1000;

  function connect() {
    if (closed) return;

    onStatusChange('connecting');

    try {
      socket = new WebSocket(url);
    } catch (err) {
      console.error('WebSocket creation failed:', err);
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      reconnectAttempts = 0;
      onStatusChange('connected');
    };

    socket.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        // Backend sends { event_type, signal } — normalize to { event, data }
        const msg: WsMessage = {
          event: raw.event_type || raw.event || 'unknown',
          data: raw.signal || raw.data || raw,
        };
        onMessage(msg);
      } catch (err) {
        console.warn('Failed to parse WS message:', event.data, err);
      }
    };

    socket.onclose = () => {
      onStatusChange('disconnected');
      if (!closed) {
        scheduleReconnect();
      }
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      socket?.close();
    };
  }

  function scheduleReconnect() {
    if (closed) return;
    const delay = Math.min(baseDelay * Math.pow(2, reconnectAttempts), maxReconnectDelay);
    reconnectAttempts++;
    onStatusChange('connecting');
    reconnectTimer = setTimeout(connect, delay);
  }

  function close() {
    closed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      socket.close();
      socket = null;
    }
    onStatusChange('disconnected');
  }

  connect();

  return { socket, close };
}

export function sendWsMessage(socket: WebSocket | null, event: string, data: unknown): void {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ event, data }));
  }
}
