import type { DashboardTheme, ThemeTone } from '../types/theme';

export interface ChartGradients {
  cct: [string, string, string, string, string];
  intensity: [string, string, string];
}

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
  accentPrimary: string;
  accentSecondary: string;
  success: string;
  danger: string;
  statIconColor: string;
  currentLine: string;
  chartGrid: string;
  chartAxis: string;
  chartBadgeBg: string;
  chartBadgeText: string;
  chartGradients: ChartGradients;
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
    pageBg: '#f9f7f3',
    cardBg: '#fffefb',
    cardBgSoft: '#f5f1ea',
    border: '#e3dbd0',
    textPrimary: '#2a2622',
    textSecondary: '#635c54',
    textMuted: '#8f8579',
    accentBlue: '#4a90b8',
    accentOrange: '#cd853f',
    accentPrimary: '#4a90b8',
    accentSecondary: '#cd853f',
    success: '#6b8e6b',
    danger: '#bc6c5c',
    statIconColor: '#6b8e6b',
    currentLine: '#4a90b8',
    chartGrid: 'rgba(227, 219, 208, 0.6)',
    chartAxis: '#8f8579',
    chartBadgeBg: 'rgba(255, 254, 251, 0.95)',
    chartBadgeText: '#2a2622',
    chartGradients: {
      cct: [
        '#4a90b8',
        '#6ba8c9',
        '#8ec0da',
        '#b1d8eb',
        '#d4f0fc',
      ],
      intensity: [
        '#c49a6cee',
        '#d4b08cbb',
        '#d4b08c10',
      ],
    },
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
    accentPrimary: '#5aa7ff',
    accentSecondary: '#f6a24e',
    success: '#32be74',
    danger: '#f1635a',
    statIconColor: '#32be74',
    currentLine: '#5aa7ff',
    chartGrid: 'rgba(75, 68, 84, 0.42)',
    chartAxis: '#a69bb8',
    chartBadgeBg: 'rgba(252, 246, 255, 0.86)',
    chartBadgeText: '#2a2332',
    chartGradients: {
      cct: [
        '#5aa7ff',
        '#4d95e8',
        '#3a7fcb',
        '#2d68a8',
        '#1a2635',
      ],
      intensity: [
        '#f6a24eee',
        '#f6b555bb',
        '#f6b55510',
      ],
    },
  },
};
