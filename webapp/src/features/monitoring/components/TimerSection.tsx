import React from 'react';
import { ChevronDown, Clock } from 'lucide-react';
import { Card } from '../../../components/Card';
import { useSystemMonitor } from '../../../hooks/useSystemMonitor';
import { useUiConfig } from '../../../hooks/useUiConfig';
import { TimeEditor } from './TimeEditor';
import { useTimerControl } from './useTimerControl';
import { formatTime } from '../../../utils/time';

interface TimerSectionProps {
  variant?: 'card' | 'content';
}

export const TimerSection: React.FC<TimerSectionProps> = ({ variant = 'card' }) => {
  const { stats } = useSystemMonitor();
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

  const timerBody = (
    <>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 field-label">
          <Clock size={14} className={isTimerEnabled ? 'timer-icon-active' : ''} />
          {uiConfig.labels.system_timer}
        </div>
        <div className="tab-shell">
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

      <div className="grid grid-cols-2 gap-2">
        <div className="relative">
          <label className="field-label block mb-1">{uiConfig.labels.on_time}</label>
          <button
            type="button"
            onClick={() => openPicker('on')}
            disabled={pickerDisabled}
            className="time-trigger motion-soft data-text w-full min-h-[52px] h-auto py-2 text-sm"
          >
            <span>{formatTime(onHour, onMinute)}</span>
            <ChevronDown size={12} />
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
            className="time-trigger motion-soft data-text w-full min-h-[52px] h-auto py-2 text-sm"
          >
            <span>{formatTime(offHour, offMinute)}</span>
            <ChevronDown size={12} />
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
      </div>

      <div className="flex gap-2 mt-2">
        <button
          onClick={() => void setTimer()}
          disabled={!isTimerEnabled || !onTime || !offTime || setPending || clearPending || togglePending}
          className="flex-1 h-11 sm:h-12 rounded text-sm font-bold motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
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
          className="flex-1 h-11 sm:h-12 rounded text-sm font-bold motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
          style={{
            border: '1px solid var(--border-color)',
            background: 'var(--action-neutral-bg)',
            color: 'var(--action-neutral-text)',
          }}
        >
          {clearPending ? '...' : uiConfig.labels.timer_clear}
        </button>
      </div>
    </>
  );

  return variant === 'card' ? (
    <Card title={uiConfig.labels.system_timer} icon={Clock} headerClassName="accent-green" className="h-full">
      <div className={`timer-shell ${isTimerEnabled ? 'enabled' : ''}`}>
        {timerBody}
      </div>
    </Card>
  ) : (
    <div className={`timer-shell ${isTimerEnabled ? 'enabled' : ''}`}>
      {timerBody}
    </div>
  );
};
