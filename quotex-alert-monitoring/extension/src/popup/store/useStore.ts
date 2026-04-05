/**
 * Quotex Alert Monitor - Popup Zustand Store
 * ALERT-ONLY: Manages popup UI state for monitoring and alerting.
 */

import { create } from "zustand";
import type { Signal, ExtensionMessage } from "../../shared/types";

interface StoreState {
  monitoring: boolean;
  connected: boolean;
  backendUrl: string;
  lastSignal: Signal | null;
  settings: {
    market_mode: string;
    expiry_profile: string;
    sound_enabled: boolean;
    min_confidence: number;
  };
  setMonitoring: (v: boolean) => void;
  setConnected: (v: boolean) => void;
  setLastSignal: (s: Signal | null) => void;
  updateSettings: (s: Partial<StoreState["settings"]>) => void;
}

export const useStore = create<StoreState>((set) => ({
  monitoring: false,
  connected: false,
  backendUrl: "http://localhost:8000",
  lastSignal: null,
  settings: {
    market_mode: "LIVE",
    expiry_profile: "1m",
    sound_enabled: true,
    min_confidence: 60,
  },

  setMonitoring: (v: boolean) => {
    set({ monitoring: v });
    // Notify background/content scripts
    chrome.runtime.sendMessage({
      type: "TOGGLE_MONITORING",
      enabled: v,
    } as ExtensionMessage).catch(() => {
      // Background may not be ready
    });
  },

  setConnected: (v: boolean) => {
    set({ connected: v });
  },

  setLastSignal: (s: Signal | null) => {
    set({ lastSignal: s });
  },

  updateSettings: (s: Partial<StoreState["settings"]>) => {
    set((state) => ({
      settings: { ...state.settings, ...s },
    }));
  },
}));
