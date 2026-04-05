import { useState, useEffect, useRef, useCallback } from 'react';
import { connectWs, WsStatus, WsMessage } from '../services/ws';
import { Signal } from '../services/api';

// Auto-detect WS URL from current page location (works with ngrok)
const WS_URL = import.meta.env.VITE_WS_URL
  ? import.meta.env.VITE_WS_URL + '/ws/alerts'
  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/alerts`;
const MAX_ALERTS = 20;

interface UseAlertsReturn {
  alerts: Signal[];
  wsStatus: WsStatus;
  latestAlert: Signal | null;
}

export function useAlerts(onNewAlert?: (signal: Signal) => void): UseAlertsReturn {
  const [alerts, setAlerts] = useState<Signal[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>('disconnected');
  const [latestAlert, setLatestAlert] = useState<Signal | null>(null);
  const onNewAlertRef = useRef(onNewAlert);
  onNewAlertRef.current = onNewAlert;

  const handleMessage = useCallback((msg: WsMessage) => {
    // Backend sends { event_type, signal } format
    const raw = msg as unknown as Record<string, unknown>;
    const eventType = (raw.event_type || raw.event || msg.event || '') as string;
    const payload = (raw.signal || raw.data || msg.data) as Signal | undefined;
    if (!payload) return;

    if (eventType === 'new_alert' || eventType === 'new_signal') {
      const signal = payload;
      setAlerts((prev) => {
        const filtered = prev.filter((s) => s.signal_id !== signal.signal_id);
        return [signal, ...filtered].slice(0, MAX_ALERTS);
      });
      setLatestAlert(signal);
      onNewAlertRef.current?.(signal);
    } else if (eventType === 'evaluation_update' || eventType === 'signal_evaluated') {
      const updated = payload;
      setAlerts((prev) =>
        prev.map((s) =>
          s.signal_id === updated.signal_id ? { ...s, ...updated } : s
        )
      );
      setLatestAlert((prev) =>
        prev && prev.signal_id === updated.signal_id ? { ...prev, ...updated } : prev
      );
    } else if (eventType === 'health_update') {
      // Health updates handled elsewhere
    }
  }, []);

  useEffect(() => {
    const conn = connectWs(WS_URL, handleMessage, setWsStatus);
    return () => conn.close();
  }, [handleMessage]);

  return { alerts, wsStatus, latestAlert };
}
