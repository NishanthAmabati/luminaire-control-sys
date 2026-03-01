import { useEffect, useState } from 'react';

export type EventSnapshot = Record<string, unknown> | null;

const SNAPSHOT_STORAGE_KEY = 'sss:lastSnapshot';

const mergeSnapshots = (prev: EventSnapshot, next: EventSnapshot): EventSnapshot => {
  if (!next || typeof next !== 'object') return next;
  if (!prev || typeof prev !== 'object') return next;

  const merged = { ...(next as Record<string, unknown>) };
  const prevScheduler = (prev as Record<string, unknown>).scheduler;
  const nextScheduler = (next as Record<string, unknown>).scheduler;

  if (prevScheduler && typeof prevScheduler === 'object') {
    const scheduler = nextScheduler && typeof nextScheduler === 'object' ? { ...nextScheduler } : {};
    if (typeof (scheduler as Record<string, unknown>).system_on !== 'boolean') {
      const prevSystemOn = (prevScheduler as Record<string, unknown>).system_on;
      if (typeof prevSystemOn === 'boolean') {
        (scheduler as Record<string, unknown>).system_on = prevSystemOn;
      }
    }
    merged.scheduler = scheduler;
  }

  return merged as EventSnapshot;
};

const loadCachedSnapshot = (): EventSnapshot => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(SNAPSHOT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as EventSnapshot) : null;
  } catch {
    return null;
  }
};

const persistSnapshot = (snapshot: EventSnapshot) => {
  if (typeof window === 'undefined') return;
  try {
    if (!snapshot || typeof snapshot !== 'object') return;
    window.localStorage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // Ignore localStorage write failures (quota, private mode).
  }
};

export const useEventSnapshot = () => {
  const gatewayHttp = import.meta.env.VITE_EVENT_GATEWAY_URL || '';
  const [snapshot, setSnapshot] = useState<EventSnapshot>(() => loadCachedSnapshot());
  const [streamError, setStreamError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let eventSource: EventSource | null = null;
    let snapshotRefreshInFlight = false;
    let refreshQueued = false;

    const refreshSnapshot = async () => {
      if (snapshotRefreshInFlight) {
        refreshQueued = true;
        return;
      }
      snapshotRefreshInFlight = true;
      try {
        const response = await fetch(`${gatewayHttp}/snapshot`);
        const payload = await response.json();
        if (!cancelled) {
          setSnapshot((prev) => {
            const merged = mergeSnapshots(prev, payload);
            persistSnapshot(merged);
            return merged;
          });
        }
      } catch (err) {
        if (!cancelled) console.error('Failed to fetch initial gateway snapshot', err);
      } finally {
        snapshotRefreshInFlight = false;
        if (refreshQueued && !cancelled) {
          refreshQueued = false;
          void refreshSnapshot();
        }
      }
    };

    const connectSse = () => {
      if (cancelled) return;
      eventSource = new EventSource(`${gatewayHttp}/events`);

      eventSource.onopen = () => {
        setStreamError(null);
      };

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload?.snapshot && typeof payload.snapshot === 'object') {
            setSnapshot((prev) => {
              const merged = mergeSnapshots(prev, payload.snapshot);
              persistSnapshot(merged);
              return merged;
            });
          } else if (payload?.type === 'heartbeat' && typeof payload?.server_time === 'number') {
            setLatencyMs(Math.max(0, Date.now() - payload.server_time));
          } else if (payload?.channel && payload?.event) {
            void refreshSnapshot();
          }
          setStreamError(null);
        } catch (err) {
          console.error('Failed to parse gateway sse payload', err);
        }
      };

      eventSource.onerror = () => {
        setStreamError('Gateway SSE stream disconnected, retrying...');
      };
    };

    void refreshSnapshot();
    connectSse();

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [gatewayHttp]);

  return { snapshot, streamError, latencyMs };
};
