import { useMemo } from 'react';
import { useSchedulerUpdates } from '../hooks/useSchedulerUpdates';

/**
 * Independent ProgressBar component that manages its own WebSocket subscription
 * and state updates without relying on parent component
 */
export const ProgressBar = ({ ws, isSystemOn, currentScene }) => {
  const schedulerState = useSchedulerUpdates(ws);

  const intervalProgressPercent = useMemo(() => {
    // When system is off, always show 0%
    if (!isSystemOn) {
      return "0.0";
    }
    
    // Use backend-provided interval_progress (percentage 0-100) directly
    if (schedulerState.interval_progress !== undefined) {
      return schedulerState.interval_progress.toFixed(1);
    }
    
    // Fallback to local calculation if backend doesn't provide it
    if (schedulerState.total_intervals === 0) {
      return "0.0";
    }
    
    return (((schedulerState.current_interval + 1) / schedulerState.total_intervals) * 100).toFixed(1);
  }, [isSystemOn, schedulerState.interval_progress, schedulerState.current_interval, schedulerState.total_intervals]);

  const sceneName = (isSystemOn && currentScene) ? currentScene.slice(0, -4) : "None";

  return (
    <div className="status-item">
      <div className="status-header">
        <span className="status-label">Scene Progress</span>
        <span className="status-value">
          {isSystemOn && schedulerState.status === 'running' ? (
            <span>Running {sceneName} - {intervalProgressPercent}%</span>
          ) : (
            <span>Idle - {intervalProgressPercent}%</span>
          )}
        </span>
      </div>
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${intervalProgressPercent}%` }}
          role="progressbar"
          aria-valuenow={intervalProgressPercent}
          aria-valuemin="0"
          aria-valuemax="100"
        ></div>
      </div>
    </div>
  );
};
