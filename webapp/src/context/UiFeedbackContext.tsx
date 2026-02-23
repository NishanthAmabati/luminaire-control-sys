import React, { useCallback, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { UiFeedbackContext } from './uiFeedback.context';

interface ErrorItem {
  id: number;
  message: string;
  durationMs: number;
}

interface SuccessItem {
  id: number;
  message: string;
  durationMs: number;
}

export const UiFeedbackProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [errors, setErrors] = useState<ErrorItem[]>([]);
  const [successes, setSuccesses] = useState<SuccessItem[]>([]);

  const pushError = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    const durationMs = 6500;
    setErrors((prev) => [...prev, { id, message, durationMs }]);
    setTimeout(() => {
      setErrors((prev) => prev.filter((item) => item.id !== id));
    }, durationMs);
  }, []);

  const pushSuccess = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    const durationMs = 4200;
    setSuccesses((prev) => [...prev, { id, message, durationMs }]);
    setTimeout(() => {
      setSuccesses((prev) => prev.filter((item) => item.id !== id));
    }, durationMs);
  }, []);

  const dismissError = useCallback((id: number) => {
    setErrors((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const dismissSuccess = useCallback((id: number) => {
    setSuccesses((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const value = useMemo(() => ({ pushError, pushSuccess }), [pushError, pushSuccess]);

  return (
    <UiFeedbackContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-3 max-w-[460px]">
        {successes.map((item) => (
          <div
            key={item.id}
            className="toast-success rounded-lg border px-4 py-3 shadow-xl flex items-start gap-3 relative overflow-hidden"
            style={{
              background: '#064e3b',
              borderColor: '#34d399',
              color: '#ecfdf5',
            }}
          >
            <p className="text-base font-semibold leading-snug flex-1">{item.message}</p>
            <button
              type="button"
              onClick={() => dismissSuccess(item.id)}
              className="opacity-80 hover:opacity-100"
              aria-label="Dismiss success"
            >
              <X size={16} />
            </button>
            <div
              className="toast-success-progress"
              style={{ animationDuration: `${item.durationMs}ms` }}
            />
          </div>
        ))}
        {errors.map((item) => (
          <div
            key={item.id}
            className="toast-error rounded-lg border px-4 py-3 shadow-xl flex items-start gap-3 relative overflow-hidden"
            style={{
              background: '#7f1d1d',
              borderColor: '#ef4444',
              color: '#fee2e2',
            }}
          >
            <p className="text-base font-semibold leading-snug flex-1">{item.message}</p>
            <button
              type="button"
              onClick={() => dismissError(item.id)}
              className="opacity-80 hover:opacity-100"
              aria-label="Dismiss error"
            >
              <X size={16} />
            </button>
            <div
              className="toast-error-progress"
              style={{ animationDuration: `${item.durationMs}ms` }}
            />
          </div>
        ))}
      </div>
    </UiFeedbackContext.Provider>
  );
};
