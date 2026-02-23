import React from 'react';

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

export const ControlSlider: React.FC<SliderProps> = ({
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
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="mb-2">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        className={`w-full slider-thumb ${colorClass}`}
        style={{
          background: `linear-gradient(to right, ${trackHex} 0%, ${trackHex} ${pct}%, var(--slider-track) ${pct}%, var(--slider-track) 100%)`,
          opacity: disabled ? 0.65 : 1,
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
        aria-label={label || unit}
      />
    </div>
  );
};
