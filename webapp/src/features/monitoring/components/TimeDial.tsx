import React, { useCallback, useRef, useState } from 'react';
import { Minus, Plus } from 'lucide-react';

export interface TimeDialProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  min?: number;
  max?: number;
  disabled?: boolean;
}

const pad = (n: number) => String(n).padStart(2, '0');

export const TimeDial: React.FC<TimeDialProps> = ({
  value,
  onChange,
  label,
  min = 0,
  max = 59,
  disabled = false,
}) => {
  const coreRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  const [dragging, setDragging] = useState(false);

  const steps = Math.max(max - min + 1, 1);
  const parsed = Number(value);
  const numeric = Number.isFinite(parsed) ? Math.min(Math.max(Math.round(parsed), min), max) : min;
  const angle = ((numeric - min) / steps) * 360;

  const setFromPointer = useCallback(
    (clientX: number, clientY: number) => {
      const el = coreRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = clientX - cx;
      const dy = clientY - cy;
      if (Math.hypot(dx, dy) < rect.width * 0.12) return;
      const angleRad = (Math.atan2(dy, dx) * 180) / Math.PI + 90;
      const degree = angleRad < 0 ? angleRad + 360 : angleRad;
      const next = min + (Math.round(degree / (360 / steps)) % steps);
      onChange(pad(next));
    },
    [min, onChange, steps],
  );

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    draggingRef.current = true;
    setDragging(true);
    setFromPointer(e.clientX, e.clientY);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current || disabled) return;
    e.preventDefault();
    setFromPointer(e.clientX, e.clientY);
  };

  const endDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    draggingRef.current = false;
    setDragging(false);
  }, []);

  const step = useCallback(
    (delta: number) => {
      if (disabled) return;
      const offset = (numeric - min + delta + steps) % steps;
      onChange(pad(min + offset));
    },
    [disabled, min, numeric, onChange, steps],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    switch (e.key) {
      case 'ArrowUp':
      case 'ArrowRight':
        e.preventDefault();
        step(1);
        break;
      case 'ArrowDown':
      case 'ArrowLeft':
        e.preventDefault();
        step(-1);
        break;
      case 'PageUp':
        e.preventDefault();
        step(5);
        break;
      case 'PageDown':
        e.preventDefault();
        step(-5);
        break;
      case 'Home':
        e.preventDefault();
        onChange(pad(min));
        break;
      case 'End':
        e.preventDefault();
        onChange(pad(max));
        break;
      default:
        break;
    }
  };

  return (
    <div className="time-dial">
      <div
        ref={coreRef}
        className={`time-dial-core dial-press${dragging ? ' dragging' : ''}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onKeyDown={handleKeyDown}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label={`${label} dial`}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={numeric}
        aria-valuetext={pad(numeric)}
        aria-disabled={disabled}
      >
        <div className="time-dial-track" />
        <div className="time-dial-thumb-wrap" style={{ transform: `rotate(${angle}deg)` }}>
          <span className="time-dial-thumb" />
        </div>
        <div className="time-dial-label">{label}</div>
        <div className="time-dial-value">{pad(numeric)}</div>
      </div>
      <div className="time-dial-steppers">
        <button
          type="button"
          className="time-dial-step"
          onClick={() => step(-1)}
          disabled={disabled}
          aria-label={`Decrease ${label}`}
        >
          <Minus size={16} />
        </button>
        <button
          type="button"
          className="time-dial-step"
          onClick={() => step(1)}
          disabled={disabled}
          aria-label={`Increase ${label}`}
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  );
};
