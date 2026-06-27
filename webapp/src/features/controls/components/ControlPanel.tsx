import React, { useState, useEffect, useRef, startTransition } from 'react';
import { Minus, Plus, Settings2, Sun, Thermometer } from 'lucide-react';
import { Card } from '../../../components/Card';
import { ControlSlider } from '../../../components/ControlSlider';
import { useUiConfig } from '../../../hooks/useUiConfig';
import { useLuminaireControl } from '../hooks/useLuminaireControl';

interface ControlPanelProps {
  variant?: 'card' | 'content';
}

export const ControlPanel: React.FC<ControlPanelProps> = ({ variant = 'card' }) => {
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

  const inner = (
    <div className="flex flex-col gap-2">
      <div className={`tab-shell ${modePulseClass}`}>
        <button
          onClick={() => handleModeToggle('MANUAL')}
          className={`tab-btn ${mode === 'MANUAL' ? 'active-green' : ''}`}
          disabled={pending.mode || !systemOn}
        >
          {pending.mode && mode === 'MANUAL' ? (
            <span className="loading-dot" />
          ) : (
            uiConfig.labels.mode_manual
          )}
        </button>
        <button
          onClick={() => handleModeToggle('AUTO')}
          className={`tab-btn ${mode === 'AUTO' ? 'active-green' : ''}`}
          disabled={pending.mode || !systemOn}
        >
          {pending.mode && mode === 'AUTO' ? (
            <span className="loading-dot" />
          ) : (
            uiConfig.labels.mode_auto
          )}
        </button>
      </div>
      {!systemOn ? (
        <p className="text-sm font-bold data-text text-right" style={{ color: 'var(--danger)' }}>
          {uiConfig.labels.power_disabled}
        </p>
      ) : null}

      {mode === 'AUTO' ? (
        <>
          <div className="soft-inset motion-soft p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <div className="field-label">{uiConfig.labels.scene_selection}</div>
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
              <option value="">{uiConfig.labels.select_scene}</option>
              {availableScenes.map((scene) => (
                <option key={scene} value={scene}>
                  {scene}
                </option>
              ))}
            </select>
            {pending.sceneLoad ? (
              <p className="mt-1 text-sm font-bold data-text" style={{ color: 'var(--text-muted)' }}>
                {uiConfig.labels.loading_scene}
              </p>
            ) : null}
          </div>

          <div className="soft-inset motion-soft p-2.5">
            <p className="text-sm font-semibold data-text" style={{ color: 'var(--text-secondary)' }}>
              {uiConfig.labels.running_label}<span>{runningScene || uiConfig.labels.scene_none}</span>
            </p>

            <div className={`mt-1.5 inline-flex items-center px-3 py-1 rounded-md text-sm font-bold uppercase tracking-wide data-text ${schedulerStatus === 'idle' ? 'status-chip status-idle' : schedulerStatus === 'pending' ? 'status-chip status-pending' : 'status-chip status-running'}`}>
              {schedulerStatus === 'idle' ? uiConfig.labels.status_idle : schedulerStatus === 'pending' ? uiConfig.labels.status_pending : uiConfig.labels.status_running}
            </div>

            {schedulerStatus === 'running' ? (
              <div className="mt-2">
                <div className="scene-progress-shell">
                  <div className="scene-progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <p className="text-sm mt-1 font-semibold data-text" style={{ color: 'var(--text-muted)' }}>
                  {uiConfig.labels.progress_label} {progress.toFixed(2)}%
                </p>
              </div>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              key={scenePulseKey}
              onClick={activateScene}
              disabled={!loadedScene || pendingActivation || pending.sceneActivate || pending.sceneLoad || !systemOn}
              className={`h-9 rounded-md text-sm font-black uppercase tracking-wide disabled:opacity-45 motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press ${runningScene ? 'scene-feedback' : ''}`}
              style={{
                background: 'var(--action-strong-bg)',
                color: 'var(--action-strong-text)',
                border: '1px solid color-mix(in oklab, var(--action-strong-bg) 72%, var(--border-color) 28%)',
              }}
            >
              {pending.sceneActivate ? <span className="loading-dot" /> : uiConfig.labels.activate}
            </button>
            <button
              onClick={deactivateScene}
              disabled={pending.sceneDeactivate || !systemOn}
              className="h-9 rounded-md text-sm font-black uppercase tracking-wide disabled:opacity-45 motion-soft data-text cursor-pointer disabled:cursor-not-allowed btn-press"
              style={{
                background: 'var(--action-neutral-bg)',
                color: 'var(--action-neutral-text)',
                border: '1px solid var(--border-color)',
              }}
            >
              {pending.sceneDeactivate ? <span className="loading-dot" /> : uiConfig.labels.deactivate}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="soft-inset motion-soft p-2.5">
            <div className="flex items-center gap-1.5 mb-1.5 field-label">
              <Thermometer size={16} />
              {uiConfig.labels.color_temperature}
            </div>
            <ControlSlider
              label={uiConfig.labels.color_temperature}
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
              {uiConfig.labels.intensity}
            </div>
            <ControlSlider
              label={uiConfig.labels.intensity}
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

          {!systemOn ? (
            <div className="soft-inset p-3 text-center">
              <p className="text-sm font-bold data-text" style={{ color: 'var(--danger)' }}>
                {uiConfig.labels.power_disabled}
              </p>
            </div>
          ) : (
          <div className="grid grid-cols-2 gap-2 min-h-0">
            <div className="soft-inset p-2.5 text-center min-w-0">
              <div className="field-label">{uiConfig.labels.cool_white}</div>
              <div className="text-2xl font-black mt-1 data-text leading-none" style={{ color: 'var(--text-primary)' }}>
                {values.cw.toFixed(1)}%
              </div>
              <div className="flex items-center justify-center gap-2 mt-2">
                <button
                  className="icon-toggle"
                  style={{ width: '28px', height: '28px' }}
                  onClick={() => adjustLight('cw', -5)}
                  disabled={!systemOn || pending.manual}
                  aria-label="Decrease cool white"
                >
                  <Minus size={14} />
                </button>
                <button
                  className="icon-toggle"
                  style={{ width: '28px', height: '28px' }}
                  onClick={() => adjustLight('cw', 5)}
                  disabled={!systemOn || pending.manual}
                  aria-label="Increase cool white"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>
            <div className="soft-inset p-2.5 text-center min-w-0">
              <div className="field-label">{uiConfig.labels.warm_white}</div>
              <div className="text-2xl font-black mt-1 data-text leading-none" style={{ color: 'var(--text-primary)' }}>
                {values.ww.toFixed(1)}%
              </div>
              <div className="flex items-center justify-center gap-2 mt-2">
                <button
                  className="icon-toggle"
                  style={{ width: '28px', height: '28px' }}
                  onClick={() => adjustLight('ww', -5)}
                  disabled={!systemOn || pending.manual}
                  aria-label="Decrease warm white"
                >
                  <Minus size={14} />
                </button>
                <button
                  className="icon-toggle"
                  style={{ width: '28px', height: '28px' }}
                  onClick={() => adjustLight('ww', 5)}
                  disabled={!systemOn || pending.manual}
                  aria-label="Increase warm white"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>
          </div>
          )}
          {pending.manual ? (
            <p className="text-right" style={{ color: 'var(--text-muted)' }}>
              <span className="loading-dot"></span>
            </p>
          ) : null}
        </>
      )}
    </div>
  );

  return variant === 'card' ? (
    <Card title={uiConfig.labels.control_panel} icon={Settings2} headerClassName="accent-green" className="h-full" contentClassName="gap-2">
      {inner}
    </Card>
  ) : inner;
};
