import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { UiFeedbackProvider } from '../../context/UiFeedbackContext';
import { useTimerControl } from '../useTimerControl';

function renderWithFeedback<T>(hook: () => T) {
  return renderHook(hook, { wrapper: UiFeedbackProvider });
}

describe('useTimerControl', () => {
  const stats = { timerEnabled: true, timerStart: '06:00', timerEnd: '18:00' };
  const apiBase = 'http://localhost:8088/api';

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('derives isTimerEnabled from stats', () => {
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));
    expect(result.current.isTimerEnabled).toBe(true);
    expect(result.current.onTime).toBe('06:00');
    expect(result.current.offTime).toBe('18:00');
  });

  it('defaults isTimerEnabled to false when stats missing', () => {
    const { result } = renderWithFeedback(() => useTimerControl(undefined, apiBase));
    expect(result.current.isTimerEnabled).toBe(false);
  });

  it('provides open/close picker', () => {
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));
    act(() => result.current.openPicker('on'));
    expect(result.current.activePicker).toBe('on');
    expect(result.current.draftHour).toBe('06');
    expect(result.current.draftMinute).toBe('00');

    act(() => result.current.closePicker());
    expect(result.current.activePicker).toBeNull();
  });

  it('applies draft time', () => {
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));
    act(() => result.current.openPicker('on'));
    act(() => result.current.setDraftHour('08'));
    act(() => result.current.setDraftMinute('30'));
    act(() => result.current.applyDraft());
    expect(result.current.onHour).toBe('08');
    expect(result.current.onMinute).toBe('30');
  });

  it('generates time label', () => {
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));
    expect(result.current.timeLabel('07', '00')).toBe('07:00');
    expect(result.current.timeLabel('', '')).toBe('Select');
  });

  it('calls fetch on handleTimerToggle', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));

    await act(async () => {
      await result.current.handleTimerToggle(true);
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${apiBase}/timer/toggle?enabled=true`,
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('calls fetch on handleSetTimer', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });
    const { result } = renderWithFeedback(() => useTimerControl(stats, apiBase));

    await act(async () => {
      await result.current.handleSetTimer();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${apiBase}/timer/configure`,
      expect.objectContaining({ method: 'POST' })
    );
  });
});
