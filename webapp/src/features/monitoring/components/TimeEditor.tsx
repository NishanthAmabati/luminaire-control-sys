import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, X } from 'lucide-react';
import { TimeDial } from './TimeDial';
import { TimeWheel } from './TimeWheel';
import { parse24Time } from '../../../utils/time';

export interface TimeEditorProps {
  target: 'on' | 'off';
  title: string;
  initialHour: string;
  initialMinute: string;
  onCancel: () => void;
  onApply: (hour: string, minute: string) => void;
}

const TOUCH_QUERY = '(pointer: coarse), (max-width: 1024px)';

const useTouchMode = () => {
  const [touch, setTouch] = useState(() => window.matchMedia(TOUCH_QUERY).matches);

  useEffect(() => {
    const mql = window.matchMedia(TOUCH_QUERY);
    const update = () => setTouch(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, []);

  return touch;
};

export const TimeEditor: React.FC<TimeEditorProps> = ({
  target,
  title,
  initialHour,
  initialMinute,
  onCancel,
  onApply,
}) => {
  const touch = useTouchMode();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const initial = parse24Time(initialHour && initialMinute ? `${initialHour}:${initialMinute}` : '');
  const [hour, setHour] = useState(initial?.hour ?? '00');
  const [minute, setMinute] = useState(initial?.minute ?? '00');

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const selector = touch ? (
    <TimeWheel
      title={title}
      hour={hour}
      minute={minute}
      onHourChange={setHour}
      onMinuteChange={setMinute}
    />
  ) : (
    <>
      <div className="time-palette-title">{title}</div>
      <div className="time-edit-grid">
        <TimeDial label="Hour" value={hour} min={0} max={23} onChange={setHour} />
        <TimeDial label="Min" value={minute} min={0} max={59} onChange={setMinute} />
      </div>
    </>
  );

  const dialog = (
    <div
      ref={dialogRef}
      className={`time-palette ${touch ? 'touch-sheet' : ''}`}
      style={touch ? undefined : target === 'on' ? { left: 0, right: 'auto' } : { right: 0, left: 'auto' }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabIndex={-1}
    >
      {selector}
      <div className="time-palette-actions">
        <button type="button" className="time-action-btn" onClick={onCancel}>
          <X size={14} /> Cancel
        </button>
        <button type="button" className="time-action-btn primary" onClick={() => onApply(hour, minute)}>
          <Check size={14} /> Apply
        </button>
      </div>
    </div>
  );

  if (!touch) return dialog;

  return createPortal(
    <div className="time-sheet-layer">
      <div className="time-sheet-backdrop" onPointerDown={onCancel} />
      {dialog}
    </div>,
    document.body,
  );
};
