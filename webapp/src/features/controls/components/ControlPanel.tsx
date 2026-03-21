import React, { useState, useEffect, useRef, startTransition } from 'react';
import { Settings2, Sun, Thermometer } from 'lucide-react';
import { Card } from '../../../components/Card';
import { ControlSlider } from '../../../components/ControlSlider';
import { useUiConfig } from '../../../hooks/useUiConfig';
import { useLuminaireControl } from '../hooks/useLuminaireControl';

export const ControlPanel: React.FC = () => {
  const {
    mode,
    systemOn,
    values,
    loadedScene,
    runningScene,
    sceneProgress,
    availableScenes,
    pending,
    updateSetting,
    toggleMode,
    adjustLight,
    loadScene,
    activateScene: activateSceneApi,
    deactivateScene: deactivateSceneApi,
  } = useLuminaireControl();
  const { config: uiConfig } = useUiConfig();
  const [pendingActivation, setPendingActivation] = useState(false);
  const [modePulseClass, setModePulseClass] = useState('');
  const [scenePulseKey, setScenePulseKey] = useState(0);
  const prevRunningSceneRef = useRef<string | null>(null);
  
  const schedulerStatus: 'idle' | 'pending' | 'running' = runningScene
    ? 'running'
    : pendingActivation
      ? 'pending'
      : 'idle';
  const progress = Number.isFinite(sceneProgress) ? Math.max(0, Math.min(100, sceneProgress)) : 0;

  useEffect(() => {
    if (runningScene && runningScene !== prevRunningSceneRef.current) {
      startTransition(() => {
        setScenePulseKey(k => k + 1);
      });
    }
    prevRunningSceneRef.current = runningScene;
  }, [runningScene]);

  const handleModeToggle = (m: 'MANUAL' | 'AUTO') => {
    const pulseClass = m === 'AUTO' ? 'mode-pulse-auto' : 'mode-pulse';
    setModePulseClass(pulseClass);
    toggleMode(m);
    setTimeout(() => setModePulseClass(''), 300);
  };

  const activateScene = async () => {
    if (!loadedScene || pending.sceneActivate) return;
    setPendingActivation(true);
    await activateSceneApi(loadedScene);
    setPendingActivation(false);
  };

  const deactivateScene = async () => {
    if (pending.sceneDeactivate) return;
    await deactivateSceneApi(runningScene || loadedScene);
    setPendingActivation(false);
  };

  return (
    <Card title="Control Panel" icon={Settings2} headerClassName="accent-blue" className="h-full" contentClassName="gap-2">
      <div className={`tab-shell ${modePulseClass}`}>
        {(['MANUAL', 'AUTO'] as const).map((m) => (
          <button
            key={m}
            onClick={() => handleModeToggle(m)}
            className={`tab-btn ${mode === m ? 'active' : ''}`}
            disabled={pending.mode || !systemOn}
          >
            {pending.mode && mode === m ? (
              <span className="loading-dot" />
            ) : (
              m
            )}
          </button>
        ))}
      </div>
      {!systemOn ? (
        <p className="text-[0.72rem] font-bold data-text text-right" style={{ color: 'var(--danger)' }}>
          System is OFF. Control options are disabled.
        </p>
      ) : null}

      {mode === 'AUTO' ? (
        <>
          <div className="soft-inset motion-soft p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <div className="field-label">SCENE SELECTION</div>
              {loadedScene && (
                <span className="scene-loaded-badge">
                  {loadedScene}
                </span>
              )}
            </div>
            <select
              value={loadedScene}
              onChange={(e) => {
                const nextScene = e.target.value;
                void loadScene(nextScene);
              }}
              disabled={pending.sceneLoad || !systemOn}
              className="w-full h-9 px-2.5 rounded-md motion-soft data-text"
              style={{
                border: '1px solid var(--border-color)',
                background: 'var(--card-bg)',
                color: 'var(--text-primary)',
              }}
            >
              <option value="">Select Scene</option>
              {availableScenes.map((scene) => (
                <option key={scene} value={scene}>
                  {scene}
                </option>
              ))}
            </select>
            {pending.sceneLoad ? (
              <p className="mt-1 text-[0.68rem] font-bold data-text" style={{ color: 'var(--text-muted)' }}>
                Loading scene...
              </p>
            ) : null}
          </div>

          <div className="soft-inset motion-soft p-2.5">
            <p className="text-[0.82rem] font-semibold data-text" style={{ color: 'var(--text-secondary)' }}>
              Running: <span>{runningScene || 'None'}</span>
            </p>

            <div className="mt-1.5 inline-flex items-center px-3 py-1 rounded-md text-[0.68rem] font-bold uppercase tracking-wide status-chip data-text">
              {schedulerStatus === 'idle' ? 'Idle' : schedulerStatus === 'pending' ? 'Pending' : 'Running'}
            </div>

            {schedulerStatus === 'running' ? (
              <div className="mt-2">
                <div className="scene-progress-shell">
                  <div className="scene-progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <p className="text-[0.7rem] mt-1 font-semibold data-text" style={{ color: 'var(--text-muted)' }}>
                  Progress {progress.toFixed(2)}%
                </p>
              </div>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              key={scenePulseKey}
              onClick={activateScene}
              disabled={!loadedScene || pendingActivation || pending.sceneActivate || pending.sceneLoad || !systemOn}
              className={`h-9 rounded-md text-[0.76rem] font-black uppercase tracking-wide disabled:opacity-45 motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press ${runningScene ? 'scene-feedback' : ''}`}
              style={{
                background: 'var(--action-strong-bg)',
                color: 'var(--action-strong-text)',
                border: '1px solid color-mix(in oklab, var(--action-strong-bg) 72%, var(--border-color) 28%)',
              }}
            >
              {pending.sceneActivate ? <span className="loading-dot" /> : 'Activate'}
            </button>
            <button
              onClick={deactivateScene}
              disabled={pending.sceneDeactivate || !systemOn}
              className="h-9 rounded-md text-[0.76rem] font-black uppercase tracking-wide disabled:opacity-45 motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
              style={{
                background: 'var(--action-neutral-bg)',
                color: 'var(--action-neutral-text)',
                border: '1px solid var(--border-color)',
              }}
            >
              {pending.sceneDeactivate ? <span className="loading-dot" /> : 'Deactivate'}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="soft-inset motion-soft p-2.5">
            <div className="flex items-center gap-1.5 mb-1.5 field-label">
              <Thermometer size={16} />
              COLOR TEMPERATURE
            </div>
            <ControlSlider
              label="Color temperature"
              value={values.cct}
              min={uiConfig.cct.min}
              max={uiConfig.cct.max}
              unit={uiConfig.cct.unit}
              colorClass="accent-blue-500"
              trackHex={uiConfig.cct.color}
              onChange={(val) => updateSetting('cct', val)}
              disabled={!systemOn}
            />
            <div className="text-right text-sm font-bold data-text" style={{ color: 'var(--text-primary)' }}>
              {values.cct} {uiConfig.cct.unit}
            </div>
          </div>

          <div className="soft-inset motion-soft p-2.5">
            <div className="flex items-center gap-1.5 mb-1.5 field-label">
              <Sun size={16} />
              INTENSITY
            </div>
            <ControlSlider
              label="Intensity"
              value={values.intensity}
              min={uiConfig.intensity.min}
              max={uiConfig.intensity.max}
              unit={uiConfig.intensity.unit}
              colorClass="accent-orange-500"
              trackHex={uiConfig.intensity.color}
              onChange={(val) => updateSetting('intensity', val)}
              disabled={!systemOn}
            />
            <div className="text-right text-sm font-bold data-text" style={{ color: 'var(--text-primary)' }}>
              {values.intensity} {uiConfig.intensity.unit}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 min-h-0">
            <div className="soft-inset p-2.5 text-center min-w-0">
              <div className="field-label">Cool White</div>
              <div className="text-2xl font-black mt-1 mb-2 data-text leading-none" style={{ color: 'var(--text-primary)' }}>
                {values.cw.toFixed(1)}%
              </div>
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => adjustLight('cw', -1)}
                  disabled={!systemOn}
                  className="h-7 w-7 rounded-md font-black motion-soft btn-press"
                  style={{ background: 'var(--card-bg-soft)', border: '1px solid var(--border-color)' }}
                >
                  -
                </button>
                <button
                  onClick={() => adjustLight('cw', 1)}
                  disabled={!systemOn}
                  className="h-7 w-7 rounded-md font-black motion-soft btn-press"
                  style={{ background: 'var(--card-bg-soft)', border: '1px solid var(--border-color)' }}
                >
                  +
                </button>
              </div>
            </div>

            <div className="soft-inset p-2.5 text-center min-w-0">
              <div className="field-label">Warm White</div>
              <div className="text-2xl font-black mt-1 mb-2 data-text leading-none" style={{ color: 'var(--text-primary)' }}>
                {values.ww.toFixed(1)}%
              </div>
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => adjustLight('ww', -1)}
                  disabled={!systemOn}
                  className="h-7 w-7 rounded-md font-black motion-soft btn-press"
                  style={{ background: 'var(--card-bg-soft)', border: '1px solid var(--border-color)' }}
                >
                  -
                </button>
                <button
                  onClick={() => adjustLight('ww', 1)}
                  disabled={!systemOn}
                  className="h-7 w-7 rounded-md font-black motion-soft btn-press"
                  style={{ background: 'var(--card-bg-soft)', border: '1px solid var(--border-color)' }}
                >
                  +
                </button>
              </div>
            </div>
          </div>
          {pending.manual ? (
            <p className="text-right" style={{ color: 'var(--text-muted)' }}>
              <span className="loading-dot"></span>
            </p>
          ) : null}
        </>
      )}
    </Card>
  );
};
