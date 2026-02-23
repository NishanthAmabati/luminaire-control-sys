// src/features/controls/hooks/useLuminaireControl.ts
import { useEffect, useRef, useState } from 'react';
import { useUiConfig } from '../../../hooks/useUiConfig';
import type { ControlMode } from '../../../types/controls';
import { useEventSnapshot } from '../../../hooks/useEventSnapshot';
import { useUiFeedback } from '../../../context/useUiFeedback';
import { readErrorMessage, unknownToMessage } from '../../../utils/apiError';

export const useLuminaireControl = () => {
  const apiBase = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';
  const { config: uiConfig } = useUiConfig();
  const { snapshot } = useEventSnapshot();
  const { pushError, pushSuccess } = useUiFeedback();
  const [mode, setMode] = useState<ControlMode>('MANUAL');
  const [systemOn, setSystemOn] = useState(true);
  const [values, setValues] = useState({
    intensity: 250,
    cct: 5000,
    cw: 25.0,
    ww: 25.0,
  });
  const [loadedScene, setLoadedScene] = useState('');
  const [runningScene, setRunningScene] = useState('');
  const [sceneProgress, setSceneProgress] = useState(0);
  const [availableScenes, setAvailableScenes] = useState<string[]>([]);
  const [pending, setPending] = useState({
    manual: false,
    mode: false,
    sceneLoad: false,
    sceneActivate: false,
    sceneDeactivate: false,
  });
  const manualSyncRef = useRef<{
    timer: number | null;
    inflight: boolean;
    queued: boolean;
    lastValues: { cct: number; intensity: number };
    editingTimer: number | null;
    editing: boolean;
  }>({
    timer: null,
    inflight: false,
    queued: false,
    lastValues: { cct: 5000, intensity: 250 },
    editingTimer: null,
    editing: false,
  });
  const configSeededRef = useRef(false);
  const sceneStateRef = useRef<{ loadedScene: string; runningScene: string }>({
    loadedScene: '',
    runningScene: '',
  });
  const sceneRevertRef = useRef<{ timer: number | null; targetScene: string | null }>({
    timer: null,
    targetScene: null,
  });

  useEffect(() => {
    if (!snapshot) return;
    const scheduler = (snapshot?.scheduler as Record<string, unknown> | undefined) ?? {};
    const runtime = (scheduler?.runtime as Record<string, unknown> | undefined) ?? {};
    const nextMode: ControlMode = scheduler?.mode === 'AUTO' ? 'AUTO' : 'MANUAL';

    const apply = () => {
      setSystemOn(Boolean(scheduler?.system_on));
      setMode(nextMode);
      const nextLoadedScene = typeof scheduler?.loaded_scene === 'string' ? scheduler.loaded_scene : '';
      const nextRunningScene = typeof scheduler?.running_scene === 'string' ? scheduler.running_scene : '';
      setLoadedScene(nextLoadedScene);
      setRunningScene(nextRunningScene);
      sceneStateRef.current = { loadedScene: nextLoadedScene, runningScene: nextRunningScene };
      setSceneProgress(Number(runtime?.progress ?? 0));
      const scenes = Array.isArray(scheduler?.available_scenes)
        ? (scheduler.available_scenes.filter((s): s is string => typeof s === 'string'))
        : [];
      setAvailableScenes(scenes);
      if (!manualSyncRef.current.editing && !pending.manual) {
        setValues((prev) => ({
          ...prev,
          cct: Number(runtime?.cct ?? prev.cct),
          intensity: Number(runtime?.lux ?? prev.intensity),
        }));
      }
    };

    const t = setTimeout(apply, 0);
    return () => clearTimeout(t);
  }, [snapshot, pending.manual]);

  useEffect(() => {
    if (configSeededRef.current) return;
    if (snapshot) return;
    configSeededRef.current = true;
    setValues((prev) => ({
      ...prev,
      cct: uiConfig.cct.default,
      intensity: uiConfig.intensity.default,
    }));
    manualSyncRef.current.lastValues = {
      cct: uiConfig.cct.default,
      intensity: uiConfig.intensity.default,
    };
  }, [uiConfig, snapshot]);

  const flushManualUpdate = async () => {
    const sync = manualSyncRef.current;
    if (sync.inflight) {
      sync.queued = true;
      return;
    }
    sync.inflight = true;
    setPending((prev) => ({ ...prev, manual: true }));

    try {
      const response = await fetch(`${apiBase}/set/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cct: sync.lastValues.cct, lux: sync.lastValues.intensity }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
    } catch (err) {
      console.error('Failed to sync manual values with backend:', err);
      pushError(`Failed to set manual values. ${unknownToMessage(err)}`);
    } finally {
      sync.inflight = false;
      if (sync.queued) {
        sync.queued = false;
        void flushManualUpdate();
      } else {
        setPending((prev) => ({ ...prev, manual: false }));
      }
    }
  };

  const updateSetting = (key: 'intensity' | 'cct', val: number) => {
    if (!systemOn || mode === 'AUTO') return;

    const nextValues = { ...values, [key]: val };
    setValues(nextValues);

    const sync = manualSyncRef.current;
    sync.lastValues = { cct: nextValues.cct, intensity: nextValues.intensity };
    sync.editing = true;
    if (sync.editingTimer) window.clearTimeout(sync.editingTimer);
    sync.editingTimer = window.setTimeout(() => {
      sync.editing = false;
    }, 400);

    if (sync.timer) window.clearTimeout(sync.timer);
    sync.timer = window.setTimeout(() => {
      sync.timer = null;
      void flushManualUpdate();
    }, 150);
  };

  const adjustLight = async (lightType: 'cw' | 'ww', delta: number) => {
    if (!systemOn || mode === 'AUTO') return;

    setValues(prev => {
      let newCw = prev.cw;
      let newWw = prev.ww;

      if (lightType === 'cw') {
        newCw = Math.max(0, Math.min(100, prev.cw + delta));
        newWw = 100 - newCw;
      } else {
        newWw = Math.max(0, Math.min(100, prev.ww + delta));
        newCw = 100 - newWw;
      }

      return { ...prev, cw: newCw, ww: newWw };
    });
  };

  useEffect(() => {
    return () => {
      const sync = manualSyncRef.current;
      if (sync.timer) window.clearTimeout(sync.timer);
      if (sync.editingTimer) window.clearTimeout(sync.editingTimer);
      const sceneRevert = sceneRevertRef.current;
      if (sceneRevert.timer) window.clearTimeout(sceneRevert.timer);
    };
  }, []);

  const toggleMode = (newMode: ControlMode) => {
    if (!systemOn || pending.mode) return;
    setPending((prev) => ({ ...prev, mode: true }));
    fetch(`${apiBase}/system/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: newMode }),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(await readErrorMessage(response));
        pushSuccess(`Mode switched to ${newMode}`);
      })
      .catch((err) => {
        console.error('Failed to set mode:', err);
        pushError(`Failed to switch mode. ${unknownToMessage(err)}`);
      })
      .finally(() => {
        setPending((prev) => ({ ...prev, mode: false }));
      });
  };

  const clearSceneRevert = () => {
    const ref = sceneRevertRef.current;
    if (ref.timer) window.clearTimeout(ref.timer);
    ref.timer = null;
    ref.targetScene = null;
  };

  const scheduleSceneRevert = (scene: string) => {
    clearSceneRevert();
    sceneRevertRef.current.targetScene = scene;
    sceneRevertRef.current.timer = window.setTimeout(() => {
      const { loadedScene: currentLoaded, runningScene: currentRunning } = sceneStateRef.current;
      if (currentLoaded !== scene) return;
      if (currentRunning) {
        void loadSceneInternal(currentRunning, false);
      } else if (currentLoaded) {
        void deactivateSceneInternal(currentLoaded, false);
      }
    }, 5000);
  };

  const loadSceneInternal = async (scene: string, scheduleRevert: boolean) => {
    if (!systemOn || !scene || pending.sceneLoad) return;
    setPending((prev) => ({ ...prev, sceneLoad: true }));
    try {
      const response = await fetch(`${apiBase}/scene/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      pushSuccess(`Scene loaded: ${scene}`);
      if (scheduleRevert) scheduleSceneRevert(scene);
    } catch (err) {
      console.error('Failed to load scene:', err);
      pushError(`Failed to load scene. ${unknownToMessage(err)}`);
    } finally {
      setPending((prev) => ({ ...prev, sceneLoad: false }));
    }
  };

  const loadScene = async (scene: string) => loadSceneInternal(scene, true);

  const activateScene = async (scene: string) => {
    if (!systemOn || !scene || pending.sceneActivate) return;
    clearSceneRevert();
    setPending((prev) => ({ ...prev, sceneActivate: true }));
    try {
      const response = await fetch(`${apiBase}/scene/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      pushSuccess(`Scene activated: ${scene}`);
    } catch (err) {
      console.error('Failed to activate scene:', err);
      pushError(`Failed to activate scene. ${unknownToMessage(err)}`);
    } finally {
      setPending((prev) => ({ ...prev, sceneActivate: false }));
    }
  };

  const deactivateSceneInternal = async (scene: string, showToast: boolean) => {
    if (!systemOn || !scene || pending.sceneDeactivate) return;
    setPending((prev) => ({ ...prev, sceneDeactivate: true }));
    try {
      const response = await fetch(`${apiBase}/scene/deactivate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene }),
      });
      if (!response.ok) throw new Error(await readErrorMessage(response));
      if (showToast) pushSuccess(`Scene deactivated: ${scene}`);
    } catch (err) {
      console.error('Failed to deactivate scene:', err);
      pushError(`Failed to deactivate scene. ${unknownToMessage(err)}`);
    } finally {
      setPending((prev) => ({ ...prev, sceneDeactivate: false }));
    }
  };

  const deactivateScene = async (scene: string) => {
    clearSceneRevert();
    await deactivateSceneInternal(scene, true);
  };

  return {
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
    activateScene,
    deactivateScene,
  };
};
