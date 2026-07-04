import { useEffect, useMemo, useState } from 'react';
import YAML from 'yaml';

export interface UiLabels {
  app_title: string;
  system_toggle: string;
  mode_manual: string;
  mode_auto: string;
  activate: string;
  deactivate: string;
  control_panel: string;
  scene_selection: string;
  select_scene: string;
  color_temperature: string;
  intensity: string;
  cool_white: string;
  warm_white: string;
  system_active: string;
  system_offline: string;
  system_off: string;
  power_disabled: string;
  reconnecting: string;
  status_timer: string;
  system_timer: string;
  timer_enabled: string;
  timer_disabled: string;
  on_time: string;
  off_time: string;
  timer_set: string;
  timer_clear: string;
  loading_scene: string;
  running_label: string;
  scene_none: string;
  status_running: string;
  status_idle: string;
  status_pending: string;
  progress_label: string;
  luminaire_title: string;
  search_luminaires: string;
  no_luminaires: string;
  total_luminaires: string;
  latency: string;
  cpu: string;
  memory: string;
  temperature: string;
  tab_controls: string;
  tab_timer: string;
  tab_luminaires: string;
}

export interface UiConfigSection {
  cct: {
    min: number;
    max: number;
    default: number;
    unit: string;
    color: string;
  };
  intensity: {
    min: number;
    max: number;
    default: number;
    unit: string;
    color: string;
  };
  polling_interval_ms: number;
  latency_interval_ms: number;
  labels: UiLabels;
}

const DEFAULT_LABELS: UiLabels = {
  app_title: 'Luminaire Control System',
  system_toggle: 'SYSTEM',
  mode_manual: 'MANUAL',
  mode_auto: 'AUTO',
  activate: 'Activate',
  deactivate: 'Deactivate',
  control_panel: 'Control Panel',
  scene_selection: 'SCENE SELECTION',
  select_scene: 'Select Scene',
  color_temperature: 'COLOR TEMPERATURE',
  intensity: 'INTENSITY',
  cool_white: 'Cool White',
  warm_white: 'Warm White',
  system_active: 'System Active',
  system_offline: 'System Offline',
  system_off: 'System OFF',
  power_disabled: 'Power is disabled',
  reconnecting: 'Attempting to reconnect...',
  status_timer: 'Status & Timer',
  system_timer: 'SYSTEM TIMER',
  timer_enabled: 'ENABLED',
  timer_disabled: 'DISABLED',
  on_time: 'ON TIME',
  off_time: 'OFF TIME',
  timer_set: 'SET',
  timer_clear: 'CLEAR',
  loading_scene: 'Loading scene...',
  running_label: 'Running: ',
  scene_none: 'None',
  status_running: 'Running',
  status_idle: 'Idle',
  status_pending: 'Pending',
  progress_label: 'Progress',
  luminaire_title: 'Connected Luminaires',
  search_luminaires: 'Search luminaires...',
  no_luminaires: 'No Luminaires Connected',
  total_luminaires: 'Total Luminaires:',
  latency: 'Latency',
  cpu: 'CPU',
  memory: 'Memory',
  temperature: 'Temperature',
  tab_controls: 'Controls',
  tab_timer: 'Timer',
  tab_luminaires: 'Connected Luminaires',
};

const DEFAULT_UI_CONFIG: UiConfigSection = {
  cct: {
    min: 2000,
    max: 7000,
    default: 5000,
    unit: 'K',
    color: '#10b981',
  },
  intensity: {
    min: 0,
    max: 700,
    default: 250,
    unit: 'lux',
    color: '#f97316',
  },
  polling_interval_ms: 2000,
  latency_interval_ms: 2000,
  labels: { ...DEFAULT_LABELS },
};

const coerceNumber = (value: unknown, fallback: number) =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback;

const coerceString = (value: unknown, fallback: string) =>
  typeof value === 'string' && value.trim().length > 0 ? value : fallback;

const normalizeLabels = (rawLabels: unknown): UiLabels => {
  const l = (rawLabels as Record<string, unknown>) || {};
  const result: Record<string, string> = {};
  for (const key of Object.keys(DEFAULT_LABELS)) {
    const val = (l as Record<string, unknown>)[key];
    result[key] = typeof val === 'string' && val.trim().length > 0 ? val : DEFAULT_LABELS[key as keyof UiLabels];
  }
  return result as unknown as UiLabels;
};

const normalizeUiConfig = (raw: unknown): UiConfigSection => {
  const ui = (raw as Record<string, unknown>)?.ui as Record<string, unknown> | undefined;
  if (!ui) return DEFAULT_UI_CONFIG;

  const cct = (ui.cct as Record<string, unknown>) || {};
  const intensity = (ui.intensity as Record<string, unknown>) || {};
  const labels = ui.labels;

  return {
    cct: {
      min: coerceNumber(cct.min, DEFAULT_UI_CONFIG.cct.min),
      max: coerceNumber(cct.max, DEFAULT_UI_CONFIG.cct.max),
      default: coerceNumber(cct.default, DEFAULT_UI_CONFIG.cct.default),
      unit: coerceString(cct.unit, DEFAULT_UI_CONFIG.cct.unit),
      color: coerceString(cct.color, DEFAULT_UI_CONFIG.cct.color),
    },
    intensity: {
      min: coerceNumber(intensity.min, DEFAULT_UI_CONFIG.intensity.min),
      max: coerceNumber(intensity.max, DEFAULT_UI_CONFIG.intensity.max),
      default: coerceNumber(intensity.default, DEFAULT_UI_CONFIG.intensity.default),
      unit: coerceString(intensity.unit, DEFAULT_UI_CONFIG.intensity.unit),
      color: coerceString(intensity.color, DEFAULT_UI_CONFIG.intensity.color),
    },
    polling_interval_ms: coerceNumber(ui.polling_interval_ms, DEFAULT_UI_CONFIG.polling_interval_ms),
    latency_interval_ms: coerceNumber(ui.latency_interval_ms, DEFAULT_UI_CONFIG.latency_interval_ms),
    labels: normalizeLabels(labels),
  };
};

export const useUiConfig = () => {
  const [config, setConfig] = useState<UiConfigSection>(DEFAULT_UI_CONFIG);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const configUrl = import.meta.env.VITE_UI_CONFIG_URL || '/config.yaml';
        const response = await fetch(configUrl, { cache: 'no-store' });
        if (!response.ok) throw new Error(`config.yaml not found (${response.status})`);
        const text = await response.text();
        const parsed = YAML.parse(text);
        if (!cancelled) {
          setConfig(normalizeUiConfig(parsed));
          setLoaded(true);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load UI config, using defaults.', err);
          setLoaded(true);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return useMemo(() => ({ config, loaded }), [config, loaded]);
};
