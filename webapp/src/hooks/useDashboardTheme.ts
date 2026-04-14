import { useEffect, useState } from 'react';
import type { DashboardTheme } from '../types/theme';
import { THEME_TOKENS } from '../config/theme.tokens';

const CSS_VAR_MAP = {
  pageBg: '--page-bg',
  cardBg: '--card-bg',
  cardBgSoft: '--card-bg-soft',
  border: '--border-color',
  textPrimary: '--text-primary',
  textSecondary: '--text-secondary',
  textMuted: '--text-muted',
  accentBlue: '--accent-blue',
  accentOrange: '--accent-orange',
  success: '--success',
  danger: '--danger',
} as const;

export const useDashboardTheme = () => {
  const [theme] = useState<DashboardTheme>('light-ivory');

  useEffect(() => {
    const root = document.documentElement;
    const tokens = THEME_TOKENS[theme];
    (Object.keys(CSS_VAR_MAP) as Array<keyof typeof CSS_VAR_MAP>).forEach((key) => {
      root.style.setProperty(CSS_VAR_MAP[key], tokens[key]);
    });
  }, [theme]);

  return { theme };
};
