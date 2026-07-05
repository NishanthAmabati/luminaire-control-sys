import React, { useEffect, useRef } from 'react';
import { Activity, Timer, Check, ChevronDown, Clock, Cpu, MemoryStick, Thermometer, X, Zap } from 'lucide-react';
import { Card } from '../../../components/Card';
import { StatItem } from '../../../components/StatItem';
import { useSystemMonitor } from '../../../hooks/useSystemMonitor';
import { useUiConfig } from '../../../hooks/useUiConfig';
import { useTimerControl } from '../../../hooks/useTimerControl';

interface StatusBoardProps {
  systemOn: boolean;
}

export const StatusBoard: React.FC<StatusBoardProps> = ({ systemOn }) => {
  const { stats, error } = useSystemMonitor();
  const { config: uiConfig } = useUiConfig();
  const apiBase = import.meta.env.VITE_API_URL || '/api';

  const {
    onHour, onMinute, offHour, offMinute,
    isTimerEnabled, timerTogglePending, timerSetPending, timerClearPending,
    onFocused, offFocused,
    activePicker, draftHour, draftMinute,
    setDraftHour, setDraftMinute,
    openPicker, closePicker, applyDraft,
    handleTimerToggle, handleSetTimer, handleClearTimer,
    timeLabel, onTime, offTime,
  } = useTimerControl(stats, apiBase);

  const dragRef = useRef<{ part: 'hour' | 'minute' | null; el: HTMLDivElement | null }>({ part: null, el: null });

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

  const updateDraftFromPointer = (part: 'hour' | 'minute', clientX: number, clientY: number, el: HTMLDivElement) => {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
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

  const isPointerNearThumb = (part: 'hour' | 'minute', clientX: number, clientY: number, el: HTMLDivElement) => {
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const radius = 49;
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
    const onUp = () => { dragRef.current = { part: null, el: null }; };
    window.addEventListener('pointermove', onMove, { passive: false });
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, []);

  const currentTime = new Date().toLocaleTimeString('en-US', {
    hour: 'numeric', minute: '2-digit', hour12: true,
  });

  return (
    <Card
      title={uiConfig.labels.status_timer}
      icon={Timer}
      headerClassName="accent-green"
      className="h-full overflow-visible"
      contentClassName="gap-3 overflow-visible"
    >
      <div className="grid grid-cols-2 gap-2">
        <StatItem icon={Activity} label={uiConfig.labels.latency} value={stats?.latency ?? '--'} unit="ms" />
        <StatItem icon={Cpu} label={uiConfig.labels.cpu} value={stats?.cpu ?? '--'} unit="%" />
        <StatItem icon={MemoryStick} label={uiConfig.labels.memory} value={stats?.memory ?? '--'} unit="%" />
        <StatItem icon={Thermometer} label={uiConfig.labels.temperature} value={stats?.temperature ?? '--'} unit="°C" />
      </div>

      <div className={`status-chip motion-soft p-3 flex items-center gap-3 ${!systemOn || error ? 'status-offline-glow' : 'status-active-glow'}`}>
        <div
          className={`h-10 w-10 rounded-full flex items-center justify-center ${systemOn && !error ? 'status-indicator-pulse' : ''}`}
          style={{ background: !systemOn || error ? 'var(--danger)' : 'var(--success)', color: 'var(--card-bg)' }}
        >
          <Zap size={18} />
        </div>
        <div>
          <p className="font-extrabold text-xl data-text" style={{ color: 'var(--text-primary)' }}>
            {!systemOn ? uiConfig.labels.system_off : error ? uiConfig.labels.system_offline : uiConfig.labels.system_active}
          </p>
          <p className="text-sm data-text" style={{ color: 'var(--text-secondary)' }}>
            {!systemOn
              ? uiConfig.labels.power_disabled
              : error
                ? uiConfig.labels.reconnecting
                : `CCT: ${Math.round(stats?.currentCct ?? 5000)}K, Intensity: ${Math.round(stats?.currentLux ?? 250)}lux, ${currentTime}`}
          </p>
        </div>
      </div>

      <div className={`timer-shell space-y-3 ${isTimerEnabled ? 'enabled' : ''}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 field-label">
            <Clock size={16} className={isTimerEnabled ? 'timer-icon-active' : ''} />
            {uiConfig.labels.system_timer}
          </div>
          <div className="tab-shell max-w-[220px] w-full">
            <button className={`tab-btn ${isTimerEnabled ? 'active-green' : ''}`}
              onClick={() => void handleTimerToggle(true)} disabled={timerTogglePending}>
              {timerTogglePending && !isTimerEnabled ? '...' : uiConfig.labels.timer_enabled}
            </button>
            <button className={`tab-btn ${!isTimerEnabled ? 'active-green' : ''}`}
              onClick={() => void handleTimerToggle(false)} disabled={timerTogglePending}>
              {timerTogglePending && isTimerEnabled ? '...' : uiConfig.labels.timer_disabled}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
          <div className="relative">
            <label className="field-label block mb-1">{uiConfig.labels.on_time}</label>
            <button type="button" onClick={() => openPicker('on')}
              disabled={!isTimerEnabled || timerSetPending || timerClearPending || timerTogglePending}
              className="time-trigger motion-soft data-text">
              <span>{timeLabel(onHour, onMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'on' && (
              <div className="time-palette">
                <div className="time-palette-title">{uiConfig.labels.on_time}</div>
                <div className="time-edit-grid">
                  {(['hour', 'minute'] as const).map((part) => (
                    <div className="time-dial" key={part}>
                      <div className="time-dial-core dial-press"
                        onPointerDown={(e) => startDialDrag(part, e)}
                        role="slider" aria-label={`${part} dial`}>
                        <div className="time-dial-track" />
                        <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle(part)}deg)` }}>
                          <span className="time-dial-thumb" />
                        </div>
                        <div className="time-dial-label">{part === 'hour' ? 'Hour' : 'Min'}</div>
                        <div className="time-dial-value">{(part === 'hour' ? draftHour : draftMinute || '00').padStart(2, '0')}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="time-palette-actions">
                  <button type="button" className="time-action-btn" onClick={closePicker}><X size={12} /> Cancel</button>
                  <button type="button" className="time-action-btn primary" onClick={applyDraft} disabled={!draftHour || !draftMinute}><Check size={12} /> Apply</button>
                </div>
              </div>
            )}
          </div>
          <div className="relative">
            <label className="field-label block mb-1">{uiConfig.labels.off_time}</label>
            <button type="button" onClick={() => openPicker('off')}
              disabled={!isTimerEnabled || timerSetPending || timerClearPending || timerTogglePending}
              className="time-trigger motion-soft data-text">
              <span>{timeLabel(offHour, offMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'off' && (
              <div className="time-palette">
                <div className="time-palette-title">{uiConfig.labels.off_time}</div>
                <div className="time-edit-grid">
                  {(['hour', 'minute'] as const).map((part) => (
                    <div className="time-dial" key={part}>
                      <div className="time-dial-core dial-press"
                        onPointerDown={(e) => startDialDrag(part, e)}
                        role="slider" aria-label={`${part} dial`}>
                        <div className="time-dial-track" />
                        <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${dialAngle(part)}deg)` }}>
                          <span className="time-dial-thumb" />
                        </div>
                        <div className="time-dial-label">{part === 'hour' ? 'Hour' : 'Min'}</div>
                        <div className="time-dial-value">{(part === 'hour' ? draftHour : draftMinute || '00').padStart(2, '0')}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="time-palette-actions">
                  <button type="button" className="time-action-btn" onClick={closePicker}><X size={12} /> Cancel</button>
                  <button type="button" className="time-action-btn primary" onClick={applyDraft} disabled={!draftHour || !draftMinute}><Check size={12} /> Apply</button>
                </div>
              </div>
            )}
          </div>
          <button onClick={() => void handleSetTimer()}
            disabled={!isTimerEnabled || !onTime || !offTime || timerSetPending || timerClearPending || timerTogglePending}
            className="h-10 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
            style={{ border: '1px solid var(--border-color)', background: 'var(--action-neutral-bg)', color: 'var(--action-neutral-text)' }}>
            {timerSetPending ? '...' : uiConfig.labels.timer_set}
          </button>
          <button onClick={() => void handleClearTimer()}
            disabled={!isTimerEnabled || (!onTime && !offTime) || timerSetPending || timerClearPending || timerTogglePending}
            className="h-10 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
            style={{ border: '1px solid var(--border-color)', background: 'var(--action-neutral-bg)', color: 'var(--action-neutral-text)' }}>
            {timerClearPending ? '...' : uiConfig.labels.timer_clear}
          </button>
        </div>
      </div>
    </Card>
  );
};
