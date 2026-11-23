import React from 'react';
import { Activity, Timer, ChevronDown, Clock, Cpu, MemoryStick, Thermometer, Zap } from 'lucide-react';
import { Card } from '../../../components/Card';
import { StatItem } from '../../../components/StatItem';
import { useSystemMonitor } from '../../../hooks/useSystemMonitor';
import { useUiConfig } from '../../../hooks/useUiConfig';
import { TimeEditor } from './TimeEditor';
import { useTimerControl } from './useTimerControl';
import { formatTime } from '../../../utils/time';

interface StatusBoardProps {
  systemOn: boolean;
}

export const StatusBoard: React.FC<StatusBoardProps> = ({ systemOn }) => {
  const { stats, error } = useSystemMonitor();
  const { config: uiConfig } = useUiConfig();
  const {
    isTimerEnabled,
    onTime,
    offTime,
    onHour,
    onMinute,
    offHour,
    offMinute,
    activePicker,
    togglePending,
    setPending,
    clearPending,
    openPicker,
    closePicker,
    applyPicker,
    toggleTimer,
    setTimer,
    clearTimer,
  } = useTimerControl(stats);

  const pickerDisabled = !isTimerEnabled || setPending || clearPending || togglePending;

  const currentTime = new Date().toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
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
            <button
              className={`tab-btn ${isTimerEnabled ? 'active-green' : ''}`}
              onClick={() => void toggleTimer(true)}
              disabled={togglePending}
            >
              {togglePending && !isTimerEnabled ? '...' : uiConfig.labels.timer_enabled}
            </button>
            <button
              className={`tab-btn ${!isTimerEnabled ? 'active-green' : ''}`}
              onClick={() => void toggleTimer(false)}
              disabled={togglePending}
            >
              {togglePending && isTimerEnabled ? '...' : uiConfig.labels.timer_disabled}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
          <div className="relative">
            <label className="field-label block mb-1">{uiConfig.labels.on_time}</label>
            <button
              type="button"
              onClick={() => openPicker('on')}
              disabled={pickerDisabled}
              className="time-trigger motion-soft data-text min-h-[52px] h-auto py-2"
            >
              <span>{formatTime(onHour, onMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'on' ? (
              <TimeEditor
                key="on"
                target="on"
                title={uiConfig.labels.on_time}
                initialHour={onHour}
                initialMinute={onMinute}
                onCancel={closePicker}
                onApply={applyPicker}
              />
            ) : null}
          </div>
          <div className="relative">
            <label className="field-label block mb-1">{uiConfig.labels.off_time}</label>
            <button
              type="button"
              onClick={() => openPicker('off')}
              disabled={pickerDisabled}
              className="time-trigger motion-soft data-text min-h-[52px] h-auto py-2"
            >
              <span>{formatTime(offHour, offMinute)}</span>
              <ChevronDown size={14} />
            </button>
            {activePicker === 'off' ? (
              <TimeEditor
                key="off"
                target="off"
                title={uiConfig.labels.off_time}
                initialHour={offHour}
                initialMinute={offMinute}
                onCancel={closePicker}
                onApply={applyPicker}
              />
            ) : null}
          </div>
          <button
            onClick={() => void setTimer()}
            disabled={!isTimerEnabled || !onTime || !offTime || setPending || clearPending || togglePending}
            className="h-11 sm:h-12 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
            style={{
              border: '1px solid var(--border-color)',
              background: 'var(--action-neutral-bg)',
              color: 'var(--action-neutral-text)',
            }}
          >
            {setPending ? '...' : uiConfig.labels.timer_set}
          </button>
          <button
            onClick={() => void clearTimer()}
            disabled={!isTimerEnabled || (!onTime && !offTime) || setPending || clearPending || togglePending}
            className="h-11 sm:h-12 rounded-lg text-sm font-black motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
            style={{
              border: '1px solid var(--border-color)',
              background: 'var(--action-neutral-bg)',
              color: 'var(--action-neutral-text)',
            }}
          >
            {clearPending ? '...' : uiConfig.labels.timer_clear}
          </button>
        </div>
      </div>
    </Card>
  );
};
