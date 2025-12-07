import { useMemo } from 'react';
import { useCurrentValues } from '../hooks/useCurrentValues';

/**
 * Independent ChartLabels component that displays current CCT and Intensity
 * Manages its own WebSocket subscription and updates independently
 */
export const ChartLabels = ({ ws }) => {
  const currentValues = useCurrentValues(ws);

  const cctLabel = useMemo(() => {
    return `Current CCT: ${currentValues.current_cct.toFixed(1)}K`;
  }, [currentValues.current_cct]);

  const intensityLabel = useMemo(() => {
    return `Current Intensity: ${currentValues.current_intensity.toFixed(1)} lux`;
  }, [currentValues.current_intensity]);

  return (
    <div className="chart-labels">
      <div className="chart-label cct-label">{cctLabel}</div>
      <div className="chart-label intensity-label">{intensityLabel}</div>
    </div>
  );
};
