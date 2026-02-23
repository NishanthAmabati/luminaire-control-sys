import type { DashboardTheme, ThemeTone } from '../types/theme';

export interface ThemeTokenSet {
  pageBg: string;
  cardBg: string;
  cardBgSoft: string;
  border: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  accentBlue: string;
  accentOrange: string;
  success: string;
  danger: string;
  currentLine: string;
  chartGrid: string;
  chartAxis: string;
  chartBadgeBg: string;
  chartBadgeText: string;
}

export interface ThemeOption {
  id: DashboardTheme;
  label: string;
  tone: ThemeTone;
}

export const THEME_OPTIONS: ThemeOption[] = [
  { id: 'light-ivory', label: 'Light Ivory', tone: 'light' },
  { id: 'dark-obsidian', label: 'Dark Obsidian', tone: 'dark' },
];

export const DEFAULT_THEME: DashboardTheme = 'light-ivory';

export const THEME_TOKENS: Record<DashboardTheme, ThemeTokenSet> = {
  'light-ivory': {
    pageBg: '#eeede9',
    cardBg: '#f8f7f3',
    cardBgSoft: '#f2f0ea',
    border: '#ddd8cb',
    textPrimary: '#2a2723',
    textSecondary: '#5b544c',
    textMuted: '#8c8378',
    accentBlue: '#3a7fcb',
    accentOrange: '#da8a34',
    success: '#3ea75f',
    danger: '#d76456',
    currentLine: '#f45b4f',
    chartGrid: 'rgba(213, 205, 190, 0.6)',
    chartAxis: '#8c8378',
    chartBadgeBg: 'rgba(255, 252, 246, 0.95)',
    chartBadgeText: '#3b342d',
  },
  'dark-obsidian': {
    pageBg: '#090809',
    cardBg: '#141315',
    cardBgSoft: '#1a191d',
    border: '#2a2730',
    textPrimary: '#f2eff4',
    textSecondary: '#c8bfd2',
    textMuted: '#887f96',
    accentBlue: '#5aa7ff',
    accentOrange: '#f6a24e',
    success: '#32be74',
    danger: '#f1635a',
    currentLine: '#ff5a4f',
    chartGrid: 'rgba(75, 68, 84, 0.42)',
    chartAxis: '#a69bb8',
    chartBadgeBg: 'rgba(252, 246, 255, 0.86)',
    chartBadgeText: '#2a2332',
  },
};
