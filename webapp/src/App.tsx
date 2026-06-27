import React, { useEffect, useState } from 'react';
import { DashboardLayout } from './layouts/DashboardLayout';
import { PortraitLayout } from './layouts/PortraitLayout';
import { useDashboardTheme } from './hooks/useDashboardTheme';
import { useUiConfig } from './hooks/useUiConfig';
import logo from './SSS.png';
import { UiFeedbackProvider } from './context/UiFeedbackContext';
import { useUiFeedback } from './context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from './utils/apiError';
import { useEventSnapshot } from './hooks/useEventSnapshot';

type Viewport = 'desktop' | 'tablet' | 'portrait' | 'mobile';

const resolveViewport = (w: number): Viewport => {
  if (w > 1024) return 'desktop';
  if (w > 768) return 'tablet';
  if (w > 480) return 'portrait';
  return 'mobile';
};

const AppShell: React.FC = () => {
  const apiBase = import.meta.env.VITE_API_URL || '/api';
  const [systemOn, setSystemOn] = useState(true);
  const [powerPending, setPowerPending] = useState(false);
  const [toggleAnimating, setToggleAnimating] = useState(false);
  const [viewport, setViewport] = useState<Viewport>(() => resolveViewport(window.innerWidth));
  const { theme } = useDashboardTheme();
  const { config: uiConfig } = useUiConfig();
  const { pushError } = useUiFeedback();
  const { snapshot } = useEventSnapshot();

  useEffect(() => {
    let mql1: MediaQueryList;
    let mql2: MediaQueryList;
    let mql3: MediaQueryList;

    // Not all browsers fire resize during orientation change, so use matchMedia
    const check = () => {
      const w = window.innerWidth;
      setViewport(resolveViewport(w));
    };

    try {
      mql1 = window.matchMedia('(min-width: 1025px)');
      mql2 = window.matchMedia('(min-width: 769px) and (max-width: 1024px)');
      mql3 = window.matchMedia('(max-width: 480px)');
      mql1.addEventListener('change', check);
      mql2.addEventListener('change', check);
      mql3.addEventListener('change', check);
    } catch {
      // fallback
      window.addEventListener('resize', check);
    }

    return () => {
      if (mql1) mql1.removeEventListener('change', check);
      if (mql2) mql2.removeEventListener('change', check);
      if (mql3) mql3.removeEventListener('change', check);
      window.removeEventListener('resize', check);
    };
  }, []);

  const compactHeader = viewport !== 'desktop';

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
    setToggleAnimating(true);

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
      setTimeout(() => setToggleAnimating(false), 200);
    }
  };

  return (
    <div className="app-shell h-dvh px-2 py-3 md:px-4 md:py-4 overflow-hidden">
      <header className={`header-panel mb-3 ${compactHeader ? 'compact' : ''} ${viewport === 'mobile' ? 'mobile-header' : ''}`}>
        <div className="flex items-center gap-2 md:gap-6">
          <a href="https://ssstec.in/" target="_blank" rel="noopener noreferrer">
            <img 
              src={logo} 
              alt="SSS" 
              className={`w-auto select-none cursor-pointer ${viewport === 'desktop' ? 'h-12 md:h-16' : 'h-8'}`} 
              draggable={false} 
            />
          </a>
          <h1 className={`font-black uppercase tracking-[0.04em] leading-none app-title-gradient ${viewport === 'desktop' ? 'text-2xl md:text-5xl' : 'text-lg'}`}>
            {uiConfig.labels.app_title}
          </h1>
        </div>

        <div className="system-toggle-wrap">
          <span className="toggle-label">{uiConfig.labels.system_toggle}</span>
          <button
            type="button"
            onClick={handleSystemToggle}
            className={`toggle-pill ${systemOn ? 'on' : 'off'} ${toggleAnimating ? 'toggle-feedback' : ''}`}
            aria-label="Toggle system"
            disabled={powerPending}
          >
            <span className="toggle-knob" />
          </button>
        </div>
      </header>

      {viewport === 'desktop' ? (
        <DashboardLayout theme={theme} />
      ) : viewport === 'tablet' ? (
        <PortraitLayout theme={theme} className="tablet-layout" />
      ) : viewport === 'mobile' ? (
        <PortraitLayout theme={theme} className="mobile-layout" />
      ) : (
        <PortraitLayout theme={theme} />
      )}
    </div>
  );
};

const App: React.FC = () => (
  <UiFeedbackProvider>
    <AppShell />
  </UiFeedbackProvider>
);

export default App;
