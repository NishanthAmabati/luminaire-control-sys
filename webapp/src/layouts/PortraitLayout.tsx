import { useEffect, useMemo, useState } from 'react';
import { Activity, Cpu, MemoryStick, Thermometer } from 'lucide-react';
import { ControlPanel } from '../features/controls/components/ControlPanel';
import { DualProfileChart } from '../features/monitoring/components/DualProfileChart';
import { ProfileChart } from '../features/monitoring/components/ProfileChart';
import { LuminaireList } from '../features/monitoring/components/LuminaireList';
import { TimerSection } from '../features/monitoring/components/TimerSection';
import { StatItem } from '../components/StatItem';
import { StatsPills } from '../features/monitoring/components/StatsPills';
import type { DashboardTheme } from '../types/theme';
import { useEventSnapshot } from '../hooks/useEventSnapshot';
import { useSystemMonitor } from '../hooks/useSystemMonitor';
import { useUiConfig } from '../hooks/useUiConfig';

interface PortraitLayoutProps {
  theme: DashboardTheme;
  className?: string;
}

export const PortraitLayout = ({ theme, className = '' }: PortraitLayoutProps) => {
  const [activeTab, setActiveTab] = useState<'controls' | 'timer' | 'luminaires'>('controls');
  const [currentHour, setCurrentHour] = useState(() => {
    const now = new Date();
    return now.getHours() + now.getMinutes() / 60;
  });
  const { snapshot: statePayload } = useEventSnapshot();
  const { stats } = useSystemMonitor();
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
  const hasSceneProfile = useMemo(() => {
    const profileCct = sceneProfile?.cct;
    const profileIntensity = sceneProfile?.intensity;
    const hasCct = Array.isArray(profileCct) && profileCct.length > 0;
    const hasIntensity = Array.isArray(profileIntensity) && profileIntensity.length > 0;
    return hasCct || hasIntensity;
  }, [sceneProfile]);

  const cctData = useMemo(() => {
    if (!systemOn) return [] as [number, number][];
    if (mode !== 'AUTO') return [] as [number, number][];
    if (!hasSceneProfile) return [] as [number, number][];
    const fromProfile =
      sceneProfile?.cct ??
      (statePayload as Record<string, unknown> | null)?.cct_profile;
    if (fromProfile && Array.isArray(fromProfile) && fromProfile.length > 0) {
      return parseSeries(fromProfile, currentCct);
    }
    return [] as [number, number][];
  }, [systemOn, mode, statePayload, sceneProfile, currentCct, hasSceneProfile]);

  const intensityData = useMemo(() => {
    if (!systemOn) return [] as [number, number][];
    if (mode !== 'AUTO') return [] as [number, number][];
    if (!hasSceneProfile) return [] as [number, number][];
    const fromProfile =
      sceneProfile?.intensity ??
      (statePayload as Record<string, unknown> | null)?.intensity_profile;
    if (fromProfile && Array.isArray(fromProfile) && fromProfile.length > 0) {
      return parseSeries(fromProfile, currentLux);
    }
    return [] as [number, number][];
  }, [systemOn, mode, statePayload, sceneProfile, currentLux, hasSceneProfile]);

  const isMobile = className.includes('mobile-layout');
  const isTablet = className.includes('tablet-layout');
  const isPlainPortrait = !isMobile && !isTablet;

  return (
    <main className={`portrait-layout ${className} overflow-hidden`}>
      {/* Charts */}
      {isMobile ? (
        <div className="portrait-section">
          <DualProfileChart
            theme={theme}
            cctData={cctData}
            cctColor={uiConfig.cct.color}
            cctUnit={uiConfig.cct.unit}
            cctMin={uiConfig.cct.min}
            cctMax={uiConfig.cct.max}
            currentCct={currentCct}
            intensityData={intensityData}
            intensityColor={uiConfig.intensity.color}
            intensityUnit={uiConfig.intensity.unit}
            intensityMin={uiConfig.intensity.min}
            intensityMax={uiConfig.intensity.max}
            currentLux={currentLux}
            currentHour={currentHour}
            clearAll={hasSystemOnFlag && !systemOn}
          />
        </div>
      ) : (
        <div className={`portrait-section ${isPlainPortrait ? 'flex flex-col gap-1' : 'grid grid-cols-2 gap-2'}`}>
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
            compactXAxis
          />
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
            compactXAxis
          />
        </div>
      )}

      {/* Tab card with pill nav */}
      <div className="portrait-section">
        <div className="portrait-tab-card">
          <div className="p-2">
            <div className="tab-shell" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              <button
                className={`tab-btn ${activeTab === 'controls' ? 'active-green' : ''}`}
                onClick={() => setActiveTab('controls')}
              >
                {uiConfig.labels.control_panel}
              </button>
              <button
                className={`tab-btn ${activeTab === 'timer' ? 'active-green' : ''}`}
                onClick={() => setActiveTab('timer')}
              >
                {uiConfig.labels.system_timer}
              </button>
              <button
                className={`tab-btn ${activeTab === 'luminaires' ? 'active-green' : ''}`}
                onClick={() => setActiveTab('luminaires')}
              >
                {uiConfig.labels.luminaire_title}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0">
              {activeTab === 'controls' && <ControlPanel variant="content" />}
              {activeTab === 'timer' && <TimerSection variant="content" />}
              {activeTab === 'luminaires' && <LuminaireList variant="content" />}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      {isMobile ? (
        <div className="portrait-section">
          <StatsPills
            latency={stats?.latency ?? '--'}
            cpu={stats?.cpu ?? '--'}
            memory={stats?.memory ?? '--'}
            temperature={stats?.temperature ?? '--'}
          />
        </div>
      ) : (
        <div className="portrait-section compact-stats">
          <StatItem icon={Activity} label={uiConfig.labels.latency} value={stats?.latency ?? '--'} unit="ms" />
          <StatItem icon={Cpu} label={uiConfig.labels.cpu} value={stats?.cpu ?? '--'} unit="%" />
          <StatItem icon={MemoryStick} label={uiConfig.labels.memory} value={stats?.memory ?? '--'} unit="%" />
          <StatItem icon={Thermometer} label={uiConfig.labels.temperature} value={stats?.temperature ?? '--'} unit="°C" />
        </div>
      )}
    </main>
  );
};
