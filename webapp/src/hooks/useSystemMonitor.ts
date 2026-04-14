import { useMemo } from 'react';
import { type SystemStats } from '../types/monitoring';
import { useEventSnapshot } from './useEventSnapshot';

export const useSystemMonitor = () => {
  const { snapshot, streamError, latencyMs } = useEventSnapshot();

  const stats = useMemo<SystemStats | null>(() => {
    if (!snapshot) return null;
    const scheduler = (snapshot?.scheduler as Record<string, unknown> | undefined) ?? {};
    const metrics = (snapshot?.metrics as Record<string, unknown> | undefined) ?? {};
    const runtime = (scheduler?.runtime as Record<string, unknown> | undefined) ?? {};
    const timer = (snapshot?.timer as Record<string, unknown> | undefined) ?? {};
    const systemOn = Boolean(scheduler?.system_on);
    const mode = (scheduler?.mode === 'AUTO' || scheduler?.mode === 'MANUAL' ? scheduler.mode : 'MANUAL') as 'AUTO' | 'MANUAL';

    return {
      latency: latencyMs !== null ? Math.round(latencyMs) : null,
      cpu: typeof metrics?.cpu === 'number' ? metrics.cpu : null,
      memory: typeof metrics?.memory === 'number' ? metrics.memory : null,
      temperature: typeof metrics?.temperature === 'number' ? metrics.temperature : null,
      currentCct: Number(runtime?.cct ?? 5000),
      currentLux: Number(runtime?.lux ?? 250),
      systemOn,
      mode,
      loadedScene: typeof scheduler?.loaded_scene === 'string' ? scheduler.loaded_scene : '',
      runningScene: typeof scheduler?.running_scene === 'string' ? scheduler.running_scene : '',
      sceneProgress: Number(runtime?.progress ?? 0),
      timerEnabled: typeof timer?.enabled === 'boolean' ? timer.enabled : undefined,
      timerStart: typeof timer?.start === 'string' ? timer.start.slice(0, 5) : '',
      timerEnd: typeof timer?.end === 'string' ? timer.end.slice(0, 5) : '',
      status: systemOn ? 'ACTIVE' : 'INACTIVE',
      lastSync: typeof snapshot?.last_updated === 'string' ? snapshot.last_updated : new Date().toISOString(),
    };
  }, [snapshot, latencyMs]);

  return { stats, error: streamError };
};
