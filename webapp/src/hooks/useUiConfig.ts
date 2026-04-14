import { useEffect, useMemo, useState } from 'react';
import YAML from 'yaml';

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
}

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
};

const coerceNumber = (value: unknown, fallback: number) =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback;

const coerceString = (value: unknown, fallback: string) =>
  typeof value === 'string' && value.trim().length > 0 ? value : fallback;

const normalizeUiConfig = (raw: unknown): UiConfigSection => {
  const ui = (raw as Record<string, unknown>)?.ui as Record<string, unknown> | undefined;
  if (!ui) return DEFAULT_UI_CONFIG;

  const cct = (ui.cct as Record<string, unknown>) || {};
  const intensity = (ui.intensity as Record<string, unknown>) || {};

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
