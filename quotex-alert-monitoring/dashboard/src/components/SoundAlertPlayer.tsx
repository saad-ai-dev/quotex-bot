import { useEffect, useRef, useState } from 'react';
import { Signal, getSignals } from '../services/api';

interface SoundAlertPlayerProps {
  latestAlert: Signal | null;
  soundEnabled: boolean;
}

// ============================================================
// WEB AUDIO - Siren, Win, Loss sounds
// ============================================================
let audioCtx: AudioContext | null = null;

function getAudioCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  return audioCtx;
}

// SIREN for new alert - loud oscillating alarm
function playSiren(isUp: boolean) {
  try {
    const ctx = getAudioCtx();
    if (ctx.state === 'suspended') ctx.resume();
    const dur = 1.5;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = isUp ? 'sawtooth' : 'square';
    gain.gain.setValueAtTime(0.6, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + dur);
    if (isUp) {
      osc.frequency.setValueAtTime(400, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(900, ctx.currentTime + 0.3);
      osc.frequency.linearRampToValueAtTime(500, ctx.currentTime + 0.6);
      osc.frequency.linearRampToValueAtTime(1000, ctx.currentTime + 0.9);
      osc.frequency.linearRampToValueAtTime(600, ctx.currentTime + 1.2);
      osc.frequency.linearRampToValueAtTime(1100, ctx.currentTime + 1.5);
    } else {
      osc.frequency.setValueAtTime(900, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(400, ctx.currentTime + 0.3);
      osc.frequency.linearRampToValueAtTime(800, ctx.currentTime + 0.6);
      osc.frequency.linearRampToValueAtTime(350, ctx.currentTime + 0.9);
      osc.frequency.linearRampToValueAtTime(700, ctx.currentTime + 1.2);
      osc.frequency.linearRampToValueAtTime(300, ctx.currentTime + 1.5);
    }
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + dur);
  } catch {}
}

// WIN sound - happy ascending major chord (C-E-G-C)
function playWinSound() {
  try {
    const ctx = getAudioCtx();
    if (ctx.state === 'suspended') ctx.resume();
    const notes = [523, 659, 784, 1047]; // C5, E5, G5, C6
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const start = ctx.currentTime + i * 0.12;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.4, start + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.01, start + 0.4);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(start); osc.stop(start + 0.4);
    });
  } catch {}
}

// LOSS sound - sad descending minor tones (slow, heavy)
function playLossSound() {
  try {
    const ctx = getAudioCtx();
    if (ctx.state === 'suspended') ctx.resume();

    // Three slow descending notes: Eb4 -> C4 -> Ab3 (minor feel)
    const notes = [
      { freq: 311, delay: 0, dur: 0.5 },      // Eb4
      { freq: 262, delay: 0.55, dur: 0.5 },    // C4
      { freq: 208, delay: 1.1, dur: 0.8 },     // Ab3 (long, fading)
    ];

    notes.forEach(({ freq, delay, dur }) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.value = freq;
      const t = ctx.currentTime + delay;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.5, t + 0.06);
      gain.gain.exponentialRampToValueAtTime(0.01, t + dur);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t); osc.stop(t + dur);
    });

    // Add a low rumble underneath for dramatic effect
    const rumble = ctx.createOscillator();
    const rGain = ctx.createGain();
    rumble.type = 'sine';
    rumble.frequency.value = 80;
    rGain.gain.setValueAtTime(0.15, ctx.currentTime);
    rGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 2.0);
    rumble.connect(rGain); rGain.connect(ctx.destination);
    rumble.start(); rumble.stop(ctx.currentTime + 2.0);
  } catch {}
}

function showNotification(title: string, body: string, tag: string) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  new Notification(title, { body, tag, requireInteraction: false });
}

// ============================================================
// COMPONENT
// ============================================================
const SoundAlertPlayer: React.FC<SoundAlertPlayerProps> = ({ latestAlert, soundEnabled }) => {
  const alertedIdsRef = useRef<Set<string>>(new Set());
  const evaluatedIdsRef = useRef<Set<string>>(new Set());
  const [toast, setToast] = useState<{ signal: Signal; type: 'alert' | 'win' | 'loss' } | null>(null);

  // Request notification permission + unlock audio on click
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    const unlock = () => { try { getAudioCtx().resume(); } catch {} };
    document.addEventListener('click', unlock);
    return () => document.removeEventListener('click', unlock);
  }, []);

  function fireNewAlert(signal: Signal) {
    if (soundEnabled) playSiren(signal.prediction_direction === 'UP');
    const asset = signal.asset_name || signal.market_type;
    showNotification(
      `${signal.prediction_direction === 'UP' ? '\u2B06\uFE0F' : '\u2B07\uFE0F'} ${signal.prediction_direction} ALERT — ${asset}`,
      `Confidence: ${signal.confidence.toFixed(1)}%  |  ${signal.expiry_profile}\n${signal.reasons?.[0] || ''}`,
      signal.signal_id,
    );
    setToast({ signal, type: 'alert' });
    setTimeout(() => setToast(prev => prev?.signal.signal_id === signal.signal_id ? null : prev), 8000);
  }

  function fireEvaluationResult(signal: Signal) {
    const isWin = signal.outcome === 'WIN';
    if (soundEnabled) {
      if (isWin) playWinSound(); else playLossSound();
    }
    const asset = signal.asset_name || signal.market_type;
    showNotification(
      `${isWin ? '\u2705' : '\u274C'} ${signal.outcome} — ${asset}`,
      `${signal.prediction_direction} signal at ${signal.confidence.toFixed(1)}% confidence`,
      `eval_${signal.signal_id}`,
    );
    setToast({ signal, type: isWin ? 'win' : 'loss' });
    setTimeout(() => setToast(prev => prev?.signal.signal_id === signal.signal_id ? null : prev), 6000);
  }

  // Poll for NEW pending alerts (siren)
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await getSignals({ status: 'PENDING', directional_only: 1, limit: 10 });
        if (!active) return;
        for (const sig of data.signals) {
          if ((sig.prediction_direction === 'UP' || sig.prediction_direction === 'DOWN') && !alertedIdsRef.current.has(sig.signal_id)) {
            alertedIdsRef.current.add(sig.signal_id);
            fireNewAlert(sig);
          }
        }
      } catch {}
    };
    poll();
    const iv = setInterval(poll, 3000);
    return () => { active = false; clearInterval(iv); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soundEnabled]);

  // Poll for RECENTLY EVALUATED signals (win/loss sound)
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await getSignals({ status: 'EVALUATED', directional_only: 1, limit: 10 });
        if (!active) return;
        for (const sig of data.signals) {
          if ((sig.outcome === 'WIN' || sig.outcome === 'LOSS') && !evaluatedIdsRef.current.has(sig.signal_id)) {
            // Only fire for signals we previously alerted on
            if (alertedIdsRef.current.has(sig.signal_id)) {
              evaluatedIdsRef.current.add(sig.signal_id);
              fireEvaluationResult(sig);
            } else {
              // First load — just mark as seen, don't replay old results
              evaluatedIdsRef.current.add(sig.signal_id);
            }
          }
        }
      } catch {}
    };
    // Start polling after 5 seconds (skip initial load)
    const timeout = setTimeout(() => {
      poll();
      const iv = setInterval(poll, 5000);
      if (!active) clearInterval(iv);
    }, 5000);
    return () => { active = false; clearTimeout(timeout); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soundEnabled]);

  // Also handle WS-delivered alerts
  useEffect(() => {
    if (!latestAlert?.signal_id) return;
    if (latestAlert.prediction_direction === 'NO_TRADE') return;
    if (latestAlert.status === 'PENDING' && !alertedIdsRef.current.has(latestAlert.signal_id)) {
      alertedIdsRef.current.add(latestAlert.signal_id);
      fireNewAlert(latestAlert);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestAlert]);

  // Bound sets
  useEffect(() => {
    const iv = setInterval(() => {
      if (alertedIdsRef.current.size > 300) alertedIdsRef.current = new Set(Array.from(alertedIdsRef.current).slice(-150));
      if (evaluatedIdsRef.current.size > 300) evaluatedIdsRef.current = new Set(Array.from(evaluatedIdsRef.current).slice(-150));
    }, 60000);
    return () => clearInterval(iv);
  }, []);

  // ============================================================
  // TOAST POPUP
  // ============================================================
  if (!toast) return null;

  const { signal: ts, type } = toast;
  const isUp = ts.prediction_direction === 'UP';

  let borderColor: string, bgGrad: string, titleText: string, titleIcon: string;

  if (type === 'win') {
    borderColor = '#3fb950';
    bgGrad = 'linear-gradient(135deg, #0a2e1a 0%, #112d18 100%)';
    titleText = 'WIN';
    titleIcon = '\u2705';
  } else if (type === 'loss') {
    borderColor = '#f85149';
    bgGrad = 'linear-gradient(135deg, #2e0a0a 0%, #2d1112 100%)';
    titleText = 'LOSS';
    titleIcon = '\u274C';
  } else {
    borderColor = isUp ? '#3fb950' : '#f85149';
    bgGrad = isUp ? 'linear-gradient(135deg, #0a2e1a 0%, #112d18 100%)' : 'linear-gradient(135deg, #2e0a0a 0%, #2d1112 100%)';
    titleText = isUp ? '\u2191 UP' : '\u2193 DOWN';
    titleIcon = '';
  }

  return (
    <div style={{
      position: 'fixed', top: 24, right: 24, zIndex: 99999, width: 380,
      background: bgGrad, border: `3px solid ${borderColor}`, borderRadius: 16,
      padding: 24, color: '#e6edf3',
      boxShadow: `0 0 40px ${borderColor}66, 0 12px 40px rgba(0,0,0,0.6)`,
      animation: 'toastSlideIn 0.3s ease-out, toastGlow 1s ease-in-out infinite alternate',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      <style>{`
        @keyframes toastSlideIn { from { transform: translateX(120%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes toastGlow {
          from { box-shadow: 0 0 20px ${borderColor}44, 0 12px 40px rgba(0,0,0,0.6); }
          to { box-shadow: 0 0 40px ${borderColor}88, 0 12px 40px rgba(0,0,0,0.6); }
        }
      `}</style>

      <button onClick={() => setToast(null)} style={{ position: 'absolute', top: 8, right: 12, background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: 20 }}>{'\u2715'}</button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{
          fontSize: type === 'alert' ? 26 : 22, fontWeight: 900, color: borderColor,
          background: `${borderColor}22`, padding: '6px 20px', borderRadius: 10,
        }}>
          {titleIcon} {titleText}
        </span>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#8b949e', letterSpacing: 2 }}>
            {type === 'alert' ? 'SIGNAL ALERT' : type === 'win' ? 'TRADE RESULT' : 'TRADE RESULT'}
          </div>
          <div style={{ fontSize: 12, color: '#8b949e' }}>{new Date(ts.created_at).toLocaleTimeString()}</div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, color: type === 'loss' ? '#f85149' : '#3fb950' }}>
            {ts.asset_name || ts.market_type}
          </div>
          <div style={{ fontSize: 13, color: '#8b949e' }}>{ts.market_type} &bull; {ts.expiry_profile}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 32, fontWeight: 900, color: borderColor }}>
            {type === 'alert' ? `${ts.confidence.toFixed(1)}%` : type === 'win' ? 'WIN' : 'LOSS'}
          </div>
          <div style={{ fontSize: 10, color: '#8b949e', letterSpacing: 1 }}>
            {type === 'alert' ? 'CONFIDENCE' : `${ts.prediction_direction} @ ${ts.confidence.toFixed(0)}%`}
          </div>
        </div>
      </div>

      {type === 'alert' && ts.reasons?.[0] && (
        <div style={{ fontSize: 13, color: '#8b949e', borderTop: '1px solid #30363d', paddingTop: 10 }}>{ts.reasons[0]}</div>
      )}
      {type === 'loss' && (
        <div style={{ fontSize: 13, color: '#f85149', borderTop: '1px solid #30363d', paddingTop: 10 }}>
          Signal did not go in predicted direction
        </div>
      )}
      {type === 'win' && (
        <div style={{ fontSize: 13, color: '#3fb950', borderTop: '1px solid #30363d', paddingTop: 10 }}>
          Signal confirmed — prediction was correct
        </div>
      )}
    </div>
  );
};

export default SoundAlertPlayer;
