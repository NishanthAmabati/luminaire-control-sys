import React, { memo, useMemo } from 'react';

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  colorClass: string;
  trackHex: string;
  disabled?: boolean;
  onChange: (val: number) => void;
}

export const ControlSlider: React.FC<SliderProps> = memo<SliderProps>(({
  label,
  value,
  min,
  max,
  unit,
  colorClass,
  trackHex,
  disabled = false,
  onChange,
}) => {
  const pct = useMemo(() => {
    return ((value - min) / (max - min)) * 100;
  }, [value, min, max]);

  const style = useMemo(() => ({
    background: `linear-gradient(to right, ${trackHex} 0%, ${trackHex} ${pct}%, var(--slider-track) ${pct}%, var(--slider-track) 100%)`,
    opacity: disabled ? 0.65 : 1,
    cursor: disabled ? 'not-allowed' : 'pointer',
  }), [trackHex, pct, disabled]);

  return (
    <div className="mb-2">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        className={`w-full slider-thumb slider-thumb-hover ${colorClass}`}
        style={style}
        aria-label={label || unit}
      />
    </div>
  );
});
