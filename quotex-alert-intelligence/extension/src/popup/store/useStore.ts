// ============================================================
// Quotex Alert Intelligence - Zustand Store
// ALERT-ONLY system - NO trade execution
// ============================================================

import { create } from "zustand";
import type {
  Settings,
  AlertEvent,
  MarketType,
  ExpiryProfile,
} from "@shared/types";

const DEFAULT_SETTINGS: Settings = {
  backend_url: "http://localhost:8000",
  monitoring_enabled: false,
  market_mode: "otc",
  expiry_profile: "short",
  min_confidence_threshold: 60,
  sound_alerts_enabled: true,
  browser_notifications_enabled: true,
  screenshot_logging_enabled: false,
  parse_interval_ms: 5000,
  use_websocket: true,
  auto_detect_market: true,
};

interface StoreState {
  settings: Settings;
  isMonitoring: boolean;
  isConnected: boolean;
  recentAlerts: AlertEvent[];
  marketType: MarketType | null;
  expiryProfile: ExpiryProfile;
  backendUrl: string;

  // Actions
  setSettings: (settings: Settings) => void;
  toggleMonitoring: () => Promise<void>;
  setConnected: (connected: boolean) => void;
  addAlert: (alert: AlertEvent) => void;
  updateSettings: (partial: Partial<Settings>) => Promise<void>;
  loadFromStorage: () => Promise<void>;
  saveToStorage: () => Promise<void>;
}

export const useStore = create<StoreState>((set, get) => ({
  settings: { ...DEFAULT_SETTINGS },
  isMonitoring: false,
  isConnected: false,
  recentAlerts: [],
  marketType: null,
  expiryProfile: "short",
  backendUrl: DEFAULT_SETTINGS.backend_url,

  setSettings: (settings: Settings) => {
    set({
      settings,
      backendUrl: settings.backend_url,
      expiryProfile: settings.expiry_profile,
    });
  },

  toggleMonitoring: async () => {
    const { isMonitoring } = get();
    const newState = !isMonitoring;

    const messageType = newState ? "START_MONITORING" : "STOP_MONITORING";
    try {
      await chrome.runtime.sendMessage({ type: messageType });
      set({ isMonitoring: newState });
    } catch (err) {
      console.error("[QAI] Toggle monitoring failed:", err);
    }
  },

  setConnected: (connected: boolean) => {
    set({ isConnected: connected });
  },

  addAlert: (alert: AlertEvent) => {
    set((state) => {
      const updated = [alert, ...state.recentAlerts];
      if (updated.length > 50) updated.length = 50;
      return { recentAlerts: updated };
    });
  },

  updateSettings: async (partial: Partial<Settings>) => {
    const { settings } = get();
    const updated = { ...settings, ...partial };
    set({
      settings: updated,
      backendUrl: updated.backend_url,
      expiryProfile: updated.expiry_profile,
    });

    try {
      await chrome.runtime.sendMessage({
        type: "SETTINGS_UPDATED",
        payload: partial,
      });
    } catch (err) {
      console.error("[QAI] Settings update failed:", err);
    }

    await get().saveToStorage();
  },

  loadFromStorage: async () => {
    try {
      const stored = await chrome.storage.local.get([
        "settings",
        "monitoringState",
        "recentAlerts",
      ]);

      const updates: Partial<StoreState> = {};

      if (stored.settings) {
        const merged = { ...DEFAULT_SETTINGS, ...stored.settings };
        updates.settings = merged;
        updates.backendUrl = merged.backend_url;
        updates.expiryProfile = merged.expiry_profile;
      }

      if (stored.monitoringState) {
        updates.isMonitoring = stored.monitoringState.is_monitoring ?? false;
        updates.isConnected = stored.monitoringState.is_connected ?? false;
        updates.marketType = stored.monitoringState.market_type ?? null;
      }

      if (stored.recentAlerts) {
        updates.recentAlerts = stored.recentAlerts;
      }

      set(updates);
    } catch (err) {
      console.error("[QAI] Load from storage failed:", err);
    }
  },

  saveToStorage: async () => {
    const { settings } = get();
    try {
      await chrome.storage.local.set({ settings });
    } catch (err) {
      console.error("[QAI] Save to storage failed:", err);
    }
  },
}));
