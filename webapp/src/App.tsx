import React, { useEffect, useState } from 'react';
import { Moon, Palette, Sun } from 'lucide-react';
import { DashboardLayout } from './layouts/DashboardLayout';
import { useDashboardTheme } from './hooks/useDashboardTheme';
import logo from './SSS.png';
import type { DashboardTheme } from './types/theme';
import { UiFeedbackProvider } from './context/UiFeedbackContext';
import { useUiFeedback } from './context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from './utils/apiError';
import { useEventSnapshot } from './hooks/useEventSnapshot';

const AppShell: React.FC = () => {
  const apiBase = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';
  const [systemOn, setSystemOn] = useState(true);
  const [powerPending, setPowerPending] = useState(false);
  const { theme, isDark, setThemeById, themeOptions } = useDashboardTheme();
  const { pushError } = useUiFeedback();
  const { snapshot } = useEventSnapshot();

  useEffect(() => {
    const scheduler = (snapshot?.scheduler as Record<string, unknown> | undefined) ?? {};
    if (typeof scheduler?.system_on === 'boolean' && !powerPending) {
      setSystemOn(scheduler.system_on);
    }
  }, [snapshot, powerPending]);

  const handleSystemToggle = async () => {
    if (powerPending) return;
    const next = !systemOn;
    setPowerPending(true);

    try {
      const response = await fetch(`${apiBase}/system/power`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ on: next }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      setSystemOn(next);
    } catch (err) {
      console.error('Failed to update system power', err);
      pushError(`Failed to toggle system power. ${unknownToMessage(err)}`);
    } finally {
      setPowerPending(false);
    }
  };

  return (
    <div className="app-shell min-h-screen px-2 py-3 md:px-4 md:py-4">
      <header className="header-panel mb-3">
        <div className="flex items-center gap-4 md:gap-6">
          <img src={logo} alt="SSS" className="h-12 md:h-16 w-auto select-none" draggable={false} />
          <h1 className="text-2xl md:text-5xl font-black uppercase tracking-[0.04em] leading-none app-title-gradient">
            Luminaire Control System
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="system-toggle-wrap">
            <span className="toggle-label">SYSTEM</span>
            <button
              type="button"
              onClick={handleSystemToggle}
              className={`toggle-pill ${systemOn ? 'on' : 'off'}`}
              aria-label="Toggle system"
              disabled={powerPending}
            >
              <span className="toggle-knob" />
            </button>
          </div>

          <div className="theme-selector-wrap">
            <div className="theme-selector-label">
              <Palette size={13} />
              THEME
            </div>
            <div className="theme-selector-input-wrap">
              <span className="theme-selector-icon">{isDark ? <Moon size={14} /> : <Sun size={14} />}</span>
              <select
                value={theme}
                onChange={(e) => setThemeById(e.target.value as DashboardTheme)}
                className="theme-selector-input data-text"
                aria-label="Choose color theme"
              >
                {themeOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </header>

      <DashboardLayout theme={theme} />
    </div>
  );
};

const App: React.FC = () => (
  <UiFeedbackProvider>
    <AppShell />
  </UiFeedbackProvider>
);

export default App;
