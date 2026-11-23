import React, { useEffect, useRef } from 'react';
import { Minus, Plus } from 'lucide-react';

export interface TimeWheelProps {
  title: string;
  hour: string;
  minute: string;
  onHourChange: (value: string) => void;
  onMinuteChange: (value: string) => void;
}

const ROW_HEIGHT = 64;

const pad = (value: number) => String(value).padStart(2, '0');
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const HOURS = Array.from({ length: 24 }, (_, index) => pad(index));
const MINUTES = Array.from({ length: 60 }, (_, index) => pad(index));

interface WheelColumnProps {
  label: string;
  values: string[];
  value: string;
  onChange: (value: string) => void;
}

const WheelColumn: React.FC<WheelColumnProps> = ({ label, values, value, onChange }) => {
  const columnRef = useRef<HTMLDivElement | null>(null);
  const index = Math.max(0, values.indexOf(value));
  const initialIndexRef = useRef(index);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const el = columnRef.current;
      if (el) el.scrollTop = initialIndexRef.current * ROW_HEIGHT;
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const moveTo = (next: number, behavior: ScrollBehavior = 'smooth') => {
    const clamped = clamp(next, 0, values.length - 1);
    columnRef.current?.scrollTo({ top: clamped * ROW_HEIGHT, behavior });
    onChange(values[clamped]);
  };

  const handleScroll = () => {
    const el = columnRef.current;
    if (!el) return;
    const next = clamp(Math.round(el.scrollTop / ROW_HEIGHT), 0, values.length - 1);
    if (values[next] === value) return;
    onChange(values[next]);
  };

  return (
    <div className="time-wheel-unit">
      <div className="time-wheel-caption">{label}</div>
      <div className="time-wheel-viewport">
        <div className="time-wheel-highlight" />
        <div
          ref={columnRef}
          className="time-wheel-column"
          onScroll={handleScroll}
          role="group"
          aria-label={`${label} scroll wheel`}
        >
          <div className="time-wheel-spacer" />
          {values.map((item, index) => (
            <button
              type="button"
              key={item}
              className={`time-wheel-row ${item === value ? 'selected' : ''}`}
              onClick={() => moveTo(index)}
              aria-label={`${label} ${item}`}
              aria-pressed={item === value}
            >
              {item}
            </button>
          ))}
          <div className="time-wheel-spacer" />
        </div>
      </div>
      <div className="time-wheel-steppers">
        <button
          type="button"
          className="time-wheel-step"
          onClick={() => moveTo(index - 1)}
          disabled={index === 0}
          aria-label={`Decrease ${label}`}
        >
          <Minus size={20} />
        </button>
        <button
          type="button"
          className="time-wheel-step"
          onClick={() => moveTo(index + 1)}
          disabled={index === values.length - 1}
          aria-label={`Increase ${label}`}
        >
          <Plus size={20} />
        </button>
      </div>
    </div>
  );
};

export const TimeWheel: React.FC<TimeWheelProps> = ({ title, hour, minute, onHourChange, onMinuteChange }) => (
  <div className="time-wheel">
    <div className="time-palette-title">{title}</div>
    <div className="time-wheel-grid">
      <WheelColumn label="HOUR" values={HOURS} value={hour} onChange={onHourChange} />
      <span className="time-wheel-colon">:</span>
      <WheelColumn label="MIN" values={MINUTES} value={minute} onChange={onMinuteChange} />
    </div>
  </div>
);
