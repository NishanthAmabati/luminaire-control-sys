import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook to subscribe to scheduler updates via WebSocket
 * Returns scheduler state that updates independently
 */
export const useSchedulerUpdates = (ws) => {
  const [schedulerState, setSchedulerState] = useState({
    status: 'idle',
    current_interval: 0,
    total_intervals: 8640,
    interval_progress: 0,
    current_cct: 0,
    current_intensity: 0
  });

  const messageHandlerRef = useRef(null);

  useEffect(() => {
    if (!ws || !ws.current) return;

    // Create message handler for this hook
    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'live_update' && data.data.scheduler) {
          setSchedulerState(prev => ({
            ...prev,
            ...(data.data.scheduler.status !== undefined && { status: data.data.scheduler.status }),
            ...(data.data.scheduler.current_interval !== undefined && { current_interval: data.data.scheduler.current_interval }),
            ...(data.data.scheduler.total_intervals !== undefined && { total_intervals: data.data.scheduler.total_intervals }),
            ...(data.data.scheduler.interval_progress !== undefined && { interval_progress: data.data.scheduler.interval_progress }),
            ...(data.data.scheduler.current_cct !== undefined && { current_cct: data.data.scheduler.current_cct })
          }));
        }
      } catch (error) {
        console.error('[useSchedulerUpdates] Error parsing message:', error);
      }
    };

    messageHandlerRef.current = handleMessage;
    ws.current.addEventListener('message', handleMessage);

    return () => {
      if (ws.current && messageHandlerRef.current) {
        ws.current.removeEventListener('message', messageHandlerRef.current);
      }
    };
  }, [ws]);

  return schedulerState;
};
