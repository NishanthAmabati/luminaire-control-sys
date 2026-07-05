import { useEffect, useState } from 'react';
import { useUiFeedback } from '../context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from '../utils/apiError';

interface TimerControl {
  onHour: string;
  onMinute: string;
  offHour: string;
  offMinute: string;
  setOnHour: (v: string) => void;
  setOnMinute: (v: string) => void;
  setOffHour: (v: string) => void;
  setOffMinute: (v: string) => void;
  isTimerEnabled: boolean;
  timerTogglePending: boolean;
  timerSetPending: boolean;
  timerClearPending: boolean;
  onFocused: boolean;
  offFocused: boolean;
  setOnFocused: (v: boolean) => void;
  setOffFocused: (v: boolean) => void;
  activePicker: 'on' | 'off' | null;
  draftHour: string;
  draftMinute: string;
  setDraftHour: (v: string) => void;
  setDraftMinute: (v: string) => void;
  suppressTimerSyncUntil: number;
  openPicker: (target: 'on' | 'off') => void;
  closePicker: () => void;
  applyDraft: () => void;
  handleTimerToggle: (enabled: boolean) => Promise<void>;
  handleSetTimer: () => Promise<void>;
  handleClearTimer: () => Promise<void>;
  timeLabel: (hour: string, minute: string) => string;
  onTime: string;
  offTime: string;
}

export const useTimerControl = (stats: Record<string, unknown> | undefined, apiBase: string): TimerControl => {
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

  const timeLabel = (hour: string, minute: string) => (hour && minute ? `${hour}:${minute}` : 'Select');

  const handleTimerToggle = async (enabled: boolean) => {
    if (timerTogglePending) return;
    setTimerTogglePending(true);
    try {
      const response = await fetch(`${apiBase}/timer/toggle?enabled=${enabled}`, { method: 'POST' });
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

  useEffect(() => {
    if (!stats) return;
    const canSync = Date.now() > suppressTimerSyncUntil && !activePicker && !timerSetPending && !timerClearPending;
    if (canSync && !onFocused && typeof stats.timerStart === 'string') {
      const [hour, minute] = stats.timerStart.split(':');
      setOnHour(hour ?? '');
      setOnMinute(minute ?? '');
    }
    if (canSync && !offFocused && typeof stats.timerEnd === 'string') {
      const [hour, minute] = stats.timerEnd.split(':');
      setOffHour(hour ?? '');
      setOffMinute(minute ?? '');
    }
  }, [stats, onFocused, offFocused, activePicker, timerSetPending, timerClearPending, suppressTimerSyncUntil]);

  return {
    onHour, onMinute, offHour, offMinute,
    setOnHour, setOnMinute, setOffHour, setOffMinute,
    isTimerEnabled, timerTogglePending, timerSetPending, timerClearPending,
    onFocused, offFocused, setOnFocused, setOffFocused,
    activePicker, draftHour, draftMinute,
    setDraftHour, setDraftMinute, suppressTimerSyncUntil,
    openPicker, closePicker, applyDraft,
    handleTimerToggle, handleSetTimer, handleClearTimer,
    timeLabel, onTime, offTime,
  };
};
