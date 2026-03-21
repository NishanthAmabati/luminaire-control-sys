import { useEffect, useMemo, useState } from 'react';
import { ControlPanel } from '../features/controls/components/ControlPanel';
import { StatusBoard } from '../features/monitoring/components/StatusBoard';
import { ProfileChart } from '../features/monitoring/components/ProfileChart';
import { LuminaireList } from '../features/monitoring/components/LuminaireList';
import type { DashboardTheme } from '../types/theme';
import { useEventSnapshot } from '../hooks/useEventSnapshot';
import { useUiConfig } from '../hooks/useUiConfig';

interface DashboardLayoutProps {
  theme: DashboardTheme;
}

export const DashboardLayout = ({ theme }: DashboardLayoutProps) => {
  const [currentHour, setCurrentHour] = useState(() => {
    const now = new Date();
    return now.getHours() + now.getMinutes() / 60;
  });
  const { snapshot: statePayload } = useEventSnapshot();
  const { config: uiConfig } = useUiConfig();

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setCurrentHour(now.getHours() + now.getMinutes() / 60);
    };
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);

  const parseSeries = (raw: unknown, fallback: number): [number, number][] => {
    if (!Array.isArray(raw) || raw.length === 0) {
      return [
        [0, fallback],
        [6, fallback],
        [12, fallback],
        [18, fallback],
        [24, fallback],
      ];
    }

    if (Array.isArray(raw[0])) {
      return (raw as unknown[])
        .map((item) => {
          const row = item as [unknown, unknown];
          return [Number(row[0]), Number(row[1])] as [number, number];
        })
        .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
    }

    return (raw as unknown[])
      .map((y, idx) => {
        const x = (24 / Math.max((raw as unknown[]).length - 1, 1)) * idx;
        return [Number(x.toFixed(2)), Number(y)] as [number, number];
      })
      .filter(([, y]) => Number.isFinite(y));
  };

  const scheduler = useMemo(
    () => ((statePayload?.scheduler as Record<string, unknown> | undefined) ?? {}),
    [statePayload],
  );
  const runtime = (scheduler?.runtime as Record<string, unknown> | undefined) ?? {};
  const sceneProfile = useMemo(
    () => ((scheduler?.scene_profile as Record<string, unknown> | undefined) ?? {}),
    [scheduler],
  );
  const mode = scheduler?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';
  const hasSystemOnFlag = typeof scheduler?.system_on === 'boolean';
  const systemOn = hasSystemOnFlag ? Boolean(scheduler.system_on) : true;
  const currentCct = systemOn ? Number(runtime?.cct ?? uiConfig.cct.default) : 0;
  const currentLux = systemOn ? Number(runtime?.lux ?? uiConfig.intensity.default) : 0;

  const cctData = useMemo(() => {
    if (!systemOn) return [] as [number, number][];
    if (mode !== 'AUTO') return [] as [number, number][];
    const fromProfile =
      sceneProfile?.cct ??
      (statePayload as Record<string, unknown> | null)?.cct_profile;
    if (fromProfile) return parseSeries(fromProfile, currentCct);
    return [
      [0, currentCct],
      [6, currentCct],
      [12, currentCct],
      [18, currentCct],
      [24, currentCct],
    ] as [number, number][];
  }, [systemOn, mode, statePayload, sceneProfile, currentCct]);

  const intensityData = useMemo(() => {
    if (!systemOn) return [] as [number, number][];
    if (mode !== 'AUTO') return [] as [number, number][];
    const fromProfile =
      sceneProfile?.intensity ??
      (statePayload as Record<string, unknown> | null)?.intensity_profile;
    if (fromProfile) return parseSeries(fromProfile, currentLux);
    return [
      [0, currentLux],
      [6, currentLux],
      [12, currentLux],
      [18, currentLux],
      [24, currentLux],
    ] as [number, number][];
  }, [systemOn, mode, statePayload, sceneProfile, currentLux]);

  return (
    <main className="max-w-[2350px] mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
        <div className="panel-stagger-1">
          <ProfileChart
            theme={theme}
            title="CCT"
            data={cctData}
            color={uiConfig.cct.color}
            unit={uiConfig.cct.unit}
            yMin={uiConfig.cct.min}
            yMax={uiConfig.cct.max}
            currentVal={currentCct}
            currentHour={currentHour}
            clearAll={hasSystemOnFlag && !systemOn}
          />
        </div>
        <div className="panel-stagger-2">
          <ProfileChart
            theme={theme}
            title="Intensity"
            data={intensityData}
            color={uiConfig.intensity.color}
            unit={uiConfig.intensity.unit}
            yMin={uiConfig.intensity.min}
            yMax={uiConfig.intensity.max}
            currentVal={currentLux}
            currentHour={currentHour}
            clearAll={hasSystemOnFlag && !systemOn}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-3 items-stretch">
        <div className="xl:col-span-4 xl:h-[460px] panel-stagger-3">
          <ControlPanel />
        </div>
        <div className="xl:col-span-4 xl:h-[460px] panel-stagger-4">
          <StatusBoard systemOn={systemOn} />
        </div>
        <div className="xl:col-span-4 xl:h-[460px] panel-stagger-5">
          <LuminaireList />
        </div>
      </div>
    </main>
  );
};
