import { useCallback, useEffect, useState } from 'react';
import type { DashboardTheme } from '../types/theme';
import { DEFAULT_THEME, THEME_OPTIONS, THEME_TOKENS } from '../config/theme.tokens';

const THEME_KEY = 'theme';
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

const getInitialTheme = (): DashboardTheme => {
  const saved = localStorage.getItem(THEME_KEY);
  return THEME_OPTIONS.some((option) => option.id === saved) ? (saved as DashboardTheme) : DEFAULT_THEME;
};

export const useDashboardTheme = () => {
  const [theme, setTheme] = useState<DashboardTheme>(getInitialTheme);
  const currentOption = THEME_OPTIONS.find((option) => option.id === theme) ?? THEME_OPTIONS[0];
  const isDark = currentOption.tone === 'dark';

  useEffect(() => {
    const root = document.documentElement;
    const tokens = THEME_TOKENS[theme];
    (Object.keys(CSS_VAR_MAP) as Array<keyof typeof CSS_VAR_MAP>).forEach((key) => {
      root.style.setProperty(CSS_VAR_MAP[key], tokens[key]);
    });
    document.documentElement.classList.toggle('dark', isDark);
    localStorage.setItem(THEME_KEY, theme);
  }, [isDark, theme]);

  const toggleTheme = useCallback(() => {
    const currentIndex = THEME_OPTIONS.findIndex((option) => option.id === theme);
    const nextIndex = (currentIndex + 1) % THEME_OPTIONS.length;
    setTheme(THEME_OPTIONS[nextIndex].id);
  }, [theme]);

  const setThemeById = useCallback((nextTheme: DashboardTheme) => {
    setTheme(nextTheme);
  }, []);

  return { theme, isDark, toggleTheme, setThemeById, themeOptions: THEME_OPTIONS };
};
