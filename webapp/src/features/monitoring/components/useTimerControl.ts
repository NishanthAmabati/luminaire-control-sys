import { useCallback, useEffect, useRef, useState } from 'react';
import { useUiFeedback } from '../../../context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from '../../../utils/apiError';
import { parse24Time, type TimeParts } from '../../../utils/time';
import { type SystemStats } from '../../../types/monitoring';

export type TimerPicker = 'on' | 'off' | null;

const apiBase = import.meta.env.VITE_API_URL || '/api';

const EMPTY_TIME: TimeParts = { hour: '', minute: '' };

interface ConfirmedTimes {
  on: TimeParts;
  off: TimeParts;
}

interface DraftTimes {
  on: TimeParts | null;
  off: TimeParts | null;
}

interface ExpectedTimes {
  start?: string;
  end?: string;
}

const sameParts = (a: TimeParts, b: TimeParts) => a.hour === b.hour && a.minute === b.minute;
const toTimeString = (parts: TimeParts) => (parts.hour && parts.minute ? `${parts.hour}:${parts.minute}` : '');

export const useTimerControl = (stats: SystemStats | null) => {
  const { pushError, pushSuccess } = useUiFeedback();
  const [confirmed, setConfirmed] = useState<ConfirmedTimes>({ on: EMPTY_TIME, off: EMPTY_TIME });
  const [drafts, setDrafts] = useState<DraftTimes>({ on: null, off: null });
  const [togglePending, setTogglePending] = useState(false);
  const [setPending, setSetPending] = useState(false);
  const [clearPending, setClearPending] = useState(false);
  const [activePicker, setActivePicker] = useState<TimerPicker>(null);
  const confirmedRef = useRef<ConfirmedTimes>(confirmed);
  const expectedRef = useRef<ExpectedTimes>({});

  const isTimerEnabled = typeof stats?.timerEnabled === 'boolean' ? stats.timerEnabled : false;

  const onParts = drafts.on ?? confirmed.on;
  const offParts = drafts.off ?? confirmed.off;
  const onHour = onParts.hour;
  const onMinute = onParts.minute;
  const offHour = offParts.hour;
  const offMinute = offParts.minute;
  const onTime = toTimeString(onParts);
  const offTime = toTimeString(offParts);

  const commitConfirmed = useCallback((next: ConfirmedTimes) => {
    confirmedRef.current = next;
    setConfirmed(next);
  }, []);

  const openPicker = useCallback((target: 'on' | 'off') => {
    setActivePicker(target);
  }, []);

  const closePicker = useCallback(() => {
    setActivePicker(null);
  }, []);

  const applyPicker = useCallback(
    (hour: string, minute: string) => {
      const next: TimeParts = { hour, minute };
      if (activePicker === 'on') {
        setDrafts((prev) => ({ ...prev, on: next }));
      } else if (activePicker === 'off') {
        setDrafts((prev) => ({ ...prev, off: next }));
      }
      setActivePicker(null);
    },
    [activePicker],
  );

  const clearTimer = useCallback(async () => {
    if (clearPending) return;
    setClearPending(true);
    try {
      const response = await fetch(`${apiBase}/timer/clear`);
      if (!response.ok) throw new Error(await readErrorMessage(response));
      expectedRef.current = { start: '', end: '' };
      commitConfirmed({ on: EMPTY_TIME, off: EMPTY_TIME });
      setDrafts({ on: null, off: null });
      pushSuccess('Timer cleared.');
    } catch (err) {
      console.error('Failed to clear timer:', err);
      pushError(`Failed to clear timer. ${unknownToMessage(err)}`);
    } finally {
      setClearPending(false);
    }
  }, [clearPending, commitConfirmed, pushError, pushSuccess]);

  const toggleTimer = useCallback(
    async (enabled: boolean) => {
      if (togglePending) return;
      setTogglePending(true);
      try {
        const response = await fetch(`${apiBase}/timer/toggle?enabled=${enabled}`, {
          method: 'POST',
        });
        if (!response.ok) throw new Error(await readErrorMessage(response));
        pushSuccess(`Timer ${enabled ? 'enabled' : 'disabled'}.`);
        if (!enabled) {
          await clearTimer();
        }
      } catch (err) {
        console.error('Failed to update timer:', err);
        pushError(`Failed to update timer enable state. ${unknownToMessage(err)}`);
      } finally {
        setTogglePending(false);
      }
    },
    [clearTimer, pushError, pushSuccess, togglePending],
  );

  const setTimer = useCallback(async () => {
    if (!onTime || !offTime || setPending || clearPending || togglePending) return;
    setSetPending(true);
    try {
      const response = await fetch(`${apiBase}/timer/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: onTime, end: offTime }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      expectedRef.current = { start: onTime, end: offTime };
      commitConfirmed({
        on: { hour: onHour, minute: onMinute },
        off: { hour: offHour, minute: offMinute },
      });
      setDrafts({ on: null, off: null });
      pushSuccess(`Timer set: ${onTime} → ${offTime}.`);
    } catch (err) {
      console.error('Failed to set timer:', err);
      pushError(`Failed to configure timer. ${unknownToMessage(err)}`);
    } finally {
      setSetPending(false);
    }
  }, [
    clearPending,
    commitConfirmed,
    offHour,
    offMinute,
    offTime,
    onHour,
    onMinute,
    onTime,
    pushError,
    pushSuccess,
    setPending,
    togglePending,
  ]);

  useEffect(() => {
    if (!stats) return;

    const startRaw = typeof stats.timerStart === 'string' ? stats.timerStart.slice(0, 5) : '';
    const endRaw = typeof stats.timerEnd === 'string' ? stats.timerEnd.slice(0, 5) : '';
    const expected = expectedRef.current;
    const current = confirmedRef.current;
    let next = current;
    let changed = false;

    const startParts = parse24Time(startRaw) ?? EMPTY_TIME;
    if (expected.start !== undefined) {
      if (startRaw === expected.start) {
        expected.start = undefined;
        if (!sameParts(current.on, startParts)) {
          next = { ...next, on: startParts };
          changed = true;
        }
      }
    } else if (!sameParts(current.on, startParts)) {
      next = { ...next, on: startParts };
      changed = true;
    }

    const endParts = parse24Time(endRaw) ?? EMPTY_TIME;
    if (expected.end !== undefined) {
      if (endRaw === expected.end) {
        expected.end = undefined;
        if (!sameParts(current.off, endParts)) {
          next = { ...next, off: endParts };
          changed = true;
        }
      }
    } else if (!sameParts(current.off, endParts)) {
      next = { ...next, off: endParts };
      changed = true;
    }

    if (changed) commitConfirmed(next);
  }, [commitConfirmed, stats]);

  return {
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
  };
};
