import React, { useEffect, useRef, useState } from 'react';
import { Activity, Timer, Check, ChevronDown, Clock, Cpu, MemoryStick, Thermometer, X, Zap } from 'lucide-react';
import { Card } from '../../../components/Card';
import { StatItem } from '../../../components/StatItem';
import { useSystemMonitor } from '../../../hooks/useSystemMonitor';
import { useUiFeedback } from '../../../context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from '../../../utils/apiError';

export const StatusBoard: React.FC = () => {
  const { stats, error } = useSystemMonitor();
  const apiBase = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';
  const { pushError, pushSuccess } = useUiFeedback();
  const [onHour, setOnHour] = useState('');
  const [onMinute, setOnMinute] = useState('');
  const [offHour, setOffHour] = useState('');
  const [offMinute, setOffMinute] = useState('');
  const [timerTogglePending, setTimerTogglePending] = useState(false);
  const [timerSetPending, setTimerSetPending] = useState(false);
  const [timerClearPending, setTimerClearPending] = useState(false);
  const [onFocused, setOnFocused] = useState(false);
  const [offFocused, setOffFocused] = useState(false);
  const [activePicker, setActivePicker] = useState<'on' | 'off' | null>(null);
  const [draftHour, setDraftHour] = useState('');
  const [draftMinute, setDraftMinute] = useState('');
  const [suppressTimerSyncUntil, setSuppressTimerSyncUntil] = useState(0);
  const dragRef = useRef<{ part: 'hour' | 'minute' | null; el: HTMLDivElement | null }>({
    part: null,
    el: null,
  });

  const isTimerEnabled = typeof stats?.timerEnabled === 'boolean' ? stats.timerEnabled : false;
  const onTime = onHour && onMinute ? `${onHour}:${onMinute}` : '';
  const offTime = offHour && offMinute ? `${offHour}:${offMinute}` : '';

  const openPicker = (target: 'on' | 'off') => {
    setActivePicker(target);
    if (target === 'on') {
      setDraftHour(onHour);
      setDraftMinute(onMinute);
      setOnFocused(true);
    } else {
      setDraftHour(offHour);
      setDraftMinute(offMinute);
      setOffFocused(true);
    }
  };
  const closePicker = () => {
    setActivePicker(null);
    setOnFocused(false);
    setOffFocused(false);
  };
  const applyDraft = () => {
    const h = Number(draftHour);
    const m = Number(draftMinute);
    if (!Number.isFinite(h) || !Number.isFinite(m) || h < 0 || h > 23 || m < 0 || m > 59) {
      pushError('Invalid time. Hour must be 00-23 and minute must be 00-59.');
      return;
    }
    const hh = String(h).padStart(2, '0');
    const mm = String(m).padStart(2, '0');
    if (activePicker === 'on') {
      setOnHour(hh);
      setOnMinute(mm);
    } else if (activePicker === 'off') {
      setOffHour(hh);
      setOffMinute(mm);
    }
    setSuppressTimerSyncUntil(Date.now() + 5000);
    closePicker();
  };
  const timeLabel = (hour: string, minute: string) => (hour && minute ? `${hour}:${minute}` : 'Select time');
  const parseDraft = (v: string, fallback = 0) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };
  const dialAngle = (part: 'hour' | 'minute') => {
    if (part === 'hour') {
      const v = parseDraft(draftHour, 0);
      return (v / 24) * 360;
    }
    const v = parseDraft(draftMinute, 0);
    return (v / 60) * 360;
  };
  const updateDraftFromPointer = (
    part: 'hour' | 'minute',
    clientX: number,
    clientY: number,
    el: HTMLDivElement,
  ) => {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
    // Prevent unstable angle jumps when cursor is very close to the center.
    if (Math.hypot(dx, dy) < 14) return;
    const angle = Math.atan2(clientY - cy, clientX - cx);
    let degree = (angle * 180) / Math.PI + 90;
    if (degree < 0) degree += 360;

    const steps = part === 'hour' ? 24 : 60;
    const stepDeg = 360 / steps;
    const value = Math.round(degree / stepDeg) % steps;
    const padded = String(value).padStart(2, '0');

    if (part === 'hour') setDraftHour(padded);
    else setDraftMinute(padded);
  };

  const isPointerNearThumb = (
    part: 'hour' | 'minute',
    clientX: number,
    clientY: number,
    el: HTMLDivElement,
  ) => {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const radius = 49; // Matches ring radius (98px / 2).
    const angleRad = (dialAngle(part) * Math.PI) / 180;
    const thumbX = cx + Math.sin(angleRad) * radius;
    const thumbY = cy - Math.cos(angleRad) * radius;
    return Math.hypot(clientX - thumbX, clientY - thumbY) <= 24;
  };

  const startDialDrag = (part: 'hour' | 'minute', e: React.PointerEvent<HTMLDivElement>) => {
    if (!isPointerNearThumb(part, e.clientX, e.clientY, e.currentTarget)) return;
    e.preventDefault();
    dragRef.current = { part, el: e.currentTarget };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const state = dragRef.current;
      if (!state.part || !state.el) return;
      e.preventDefault();
      updateDraftFromPointer(state.part, e.clientX, e.clientY, state.el);
    };
    const onUp = () => {
      dragRef.current = { part: null, el: null };
    };

    window.addEventListener('pointermove', onMove, { passive: false });
    window.addEventListener('pointerup', onUp);

    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, []);

  const handleTimerToggle = async (enabled: boolean) => {
    if (timerTogglePending) return;
    setTimerTogglePending(true);
    try {
      const response = await fetch(`${apiBase}/timer/toggle?enabled=${enabled}`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      setSuppressTimerSyncUntil(Date.now() + 1200);
      pushSuccess(`Timer ${enabled ? 'enabled' : 'disabled'}.`);
      if (!enabled) {
        const clearResponse = await fetch(`${apiBase}/timer/clear`);
        if (!clearResponse.ok) throw new Error(await readErrorMessage(clearResponse));
        setOnHour('');
        setOnMinute('');
        setOffHour('');
        setOffMinute('');
        setSuppressTimerSyncUntil(Date.now() + 2000);
        pushSuccess('Timer cleared.');
      }
    } catch (err) {
      console.error('Failed to update timer:', err);
      pushError(`Failed to update timer enable state. ${unknownToMessage(err)}`);
    } finally {
      setTimerTogglePending(false);
    }
  };

  const handleSetTimer = async () => {
    if (!onTime || !offTime) return;
    if (timerSetPending) return;
    setTimerSetPending(true);
    try {
      const response = await fetch(`${apiBase}/timer/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: onTime, end: offTime }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      pushSuccess(`Timer set: ${onTime} → ${offTime}.`);
    } catch (err) {
      console.error('Failed to set timer:', err);
      pushError(`Failed to configure timer. ${unknownToMessage(err)}`);
    } finally {
      setTimerSetPending(false);
    }
  };

  const handleClearTimer = async () => {
    if (timerClearPending) return;
    setTimerClearPending(true);
    try {
      const response = await fetch(`${apiBase}/timer/clear`);
      if (!response.ok) throw new Error(await readErrorMessage(response));
      setOnHour('');
      setOnMinute('');
      setOffHour('');
      setOffMinute('');
      setSuppressTimerSyncUntil(Date.now() + 2000);
      pushSuccess('Timer cleared.');
    } catch (err) {
      console.error('Failed to clear timer:', err);
      pushError(`Failed to clear timer. ${unknownToMessage(err)}`);
    } finally {
      setTimerClearPending(false);
    }
  };

  const currentTime = new Date().toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  React.useEffect(() => {
    if (!stats) return;
    const canSyncFromBackend =
      Date.now() > suppressTimerSyncUntil && !activePicker && !timerSetPending && !timerClearPending;
    if (canSyncFromBackend && !onFocused && typeof stats.timerStart === 'string') {
      const [hour, minute] = stats.timerStart.split(':');
      setOnHour(hour ?? '');
      setOnMinute(minute ?? '');
    }
    if (canSyncFromBackend && !offFocused && typeof stats.timerEnd === 'string') {
      const [hour, minute] = stats.timerEnd.split(':');
      setOffHour(hour ?? '');
      setOffMinute(minute ?? '');
    }
  }, [stats, onFocused, offFocused, activePicker, timerSetPending, timerClearPending, suppressTimerSyncUntil]);

  return (
    <Card
      title="Status & Timer"
      icon={Timer}
      className="h-full overflow-visible"
      contentClassName="gap-3 overflow-visible"
    >
      <div className="grid grid-cols-2 gap-2">
        <StatItem icon={Activity} label="Latency" value={stats?.latency ?? '--'} unit="ms" />
        <StatItem icon={Cpu} label="CPU" value={stats?.cpu ?? '--'} unit="%" />
        <StatItem icon={MemoryStick} label="Memory" value={stats?.memory ?? '--'} unit="%" />
        <StatItem icon={Thermometer} label="Temperature" value={stats?.temperature ?? '--'} unit="°C" />
      </div>

      <div className="status-chip motion-soft p-3 flex items-center gap-3">
        <div
          className="h-10 w-10 rounded-full flex items-center justify-center"
          style={{ background: error ? 'var(--danger)' : 'var(--success)', color: '#fff' }}
        >
          <Zap size={18} />
        </div>
        <div>
          <p className="font-extrabold text-2xl data-text" style={{ color: 'var(--text-primary)' }}>
            {error ? 'System Offline' : 'System Active'}
          </p>
          <p className="text-sm data-text" style={{ color: 'var(--text-secondary)' }}>
            {error
              ? 'Attempting to reconnect...'
              : `CCT: ${Math.round(stats?.currentCct ?? 5000)}K, Intensity: ${Math.round(stats?.currentLux ?? 250)}lux, ${currentTime}`}
          </p>
        </div>
      </div>

      <div className={`timer-shell space-y-3 ${isTimerEnabled ? 'enabled' : ''}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 field-label">
            <Clock size={16} />
            SYSTEM TIMER
          </div>
          <div className="tab-shell max-w-[220px] w-full">
            <button
              className={`tab-btn ${isTimerEnabled ? 'active' : ''}`}
              onClick={() => void handleTimerToggle(true)}
              disabled={timerTogglePending}
              style={
                isTimerEnabled
                  ? {
                      background: 'color-mix(in oklab, var(--success) 24%, var(--card-bg-soft) 76%)',
                      color: 'color-mix(in oklab, var(--success) 72%, var(--text-primary) 28%)',
                      border: '1px solid color-mix(in oklab, var(--success) 30%, var(--border-color) 70%)',
                    }
                  : undefined
              }
            >
              {timerTogglePending && !isTimerEnabled ? 'LOADING...' : 'ENABLED'}
            </button>
            <button
              className={`tab-btn ${!isTimerEnabled ? 'active' : ''}`}
              onClick={() => void handleTimerToggle(false)}
              disabled={timerTogglePending}
            >
              {timerTogglePending && isTimerEnabled ? 'LOADING...' : 'DISABLED'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
          <div className="relative">
            <label className="field-label block mb-1">ON TIME</label>
            <button
              type="button"
              onClick={() => openPicker('on')}
              disabled={!isTimerEnabled || timerSetPending || timerClearPending || timerTogglePending}
              className="time-trigger motion-soft data-text"
            >
              <span>{timeLabel(onHour, onMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'on' ? (
              <div className="time-palette">
                <div className="time-palette-title">ON TIME</div>
                <div className="time-edit-grid">
                  <div className="time-dial">
                    <div
                      className="time-dial-core"
                      onPointerDown={(e) => startDialDrag('hour', e)}
                      role="slider"
                      aria-label="Hour dial"
                    >
                      <div className="time-dial-track" />
                      <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle('hour')}deg)` }}>
                        <span className="time-dial-thumb" />
                      </div>
                      <div className="time-dial-label">Hour</div>
                      <div className="time-dial-value">{(draftHour || '00').padStart(2, '0')}</div>
                    </div>
                  </div>
                  <div className="time-dial">
                    <div
                      className="time-dial-core"
                      onPointerDown={(e) => startDialDrag('minute', e)}
                      role="slider"
                      aria-label="Minute dial"
                    >
                      <div className="time-dial-track" />
                      <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle('minute')}deg)` }}>
                        <span className="time-dial-thumb" />
                      </div>
                      <div className="time-dial-label">Minute</div>
                      <div className="time-dial-value">{(draftMinute || '00').padStart(2, '0')}</div>
                    </div>
                  </div>
                </div>
                <div className="time-palette-actions">
                  <button type="button" className="time-action-btn" onClick={closePicker}>
                    <X size={12} /> Cancel
                  </button>
                  <button type="button" className="time-action-btn primary" onClick={applyDraft} disabled={!draftHour || !draftMinute}>
                    <Check size={12} /> Apply
                  </button>
                </div>
              </div>
            ) : null}
          </div>
          <div className="relative">
            <label className="field-label block mb-1">OFF TIME</label>
            <button
              type="button"
              onClick={() => openPicker('off')}
              disabled={!isTimerEnabled || timerSetPending || timerClearPending || timerTogglePending}
              className="time-trigger motion-soft data-text"
            >
              <span>{timeLabel(offHour, offMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'off' ? (
              <div className="time-palette">
                <div className="time-palette-title">OFF TIME</div>
                <div className="time-edit-grid">
                  <div className="time-dial">
                    <div
                      className="time-dial-core"
                      onPointerDown={(e) => startDialDrag('hour', e)}
                      role="slider"
                      aria-label="Hour dial"
                    >
                      <div className="time-dial-track" />
                      <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle('hour')}deg)` }}>
                        <span className="time-dial-thumb" />
                      </div>
                      <div className="time-dial-label">Hour</div>
                      <div className="time-dial-value">{(draftHour || '00').padStart(2, '0')}</div>
                    </div>
                  </div>
                  <div className="time-dial">
                    <div
                      className="time-dial-core"
                      onPointerDown={(e) => startDialDrag('minute', e)}
                      role="slider"
                      aria-label="Minute dial"
                    >
                      <div className="time-dial-track" />
                      <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle('minute')}deg)` }}>
                        <span className="time-dial-thumb" />
                      </div>
                      <div className="time-dial-label">Minute</div>
                      <div className="time-dial-value">{(draftMinute || '00').padStart(2, '0')}</div>
                    </div>
                  </div>
                </div>
                <div className="time-palette-actions">
                  <button type="button" className="time-action-btn" onClick={closePicker}>
                    <X size={12} /> Cancel
                  </button>
                  <button type="button" className="time-action-btn primary" onClick={applyDraft} disabled={!draftHour || !draftMinute}>
                    <Check size={12} /> Apply
                  </button>
                </div>
              </div>
            ) : null}
          </div>
          <button
            onClick={() => void handleSetTimer()}
            disabled={!isTimerEnabled || !onTime || !offTime || timerSetPending || timerClearPending || timerTogglePending}
            className="h-10 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed"
            style={{
              border: '1px solid var(--border-color)',
              background: 'var(--action-neutral-bg)',
              color: 'var(--action-neutral-text)',
            }}
          >
            {timerSetPending ? 'LOADING...' : 'SET'}
          </button>
          <button
            onClick={() => void handleClearTimer()}
            disabled={!isTimerEnabled || (!onTime && !offTime) || timerSetPending || timerClearPending || timerTogglePending}
            className="h-10 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed"
            style={{
              border: '1px solid var(--border-color)',
              background: 'var(--action-neutral-bg)',
              color: 'var(--action-neutral-text)',
            }}
          >
            {timerClearPending ? 'LOADING...' : 'CLEAR'}
          </button>
        </div>
      </div>
    </Card>
  );
};
