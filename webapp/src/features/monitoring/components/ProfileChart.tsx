import ReactECharts from 'echarts-for-react';
import { THEME_TOKENS } from '../../../config/theme.tokens';
import type { DashboardTheme } from '../../../types/theme';
import * as echarts from 'echarts';

interface ProfileChartProps {
  theme: DashboardTheme;
  title: string;
  data: [number, number][];
  color: string;
  unit: string;
  yMin: number;
  yMax: number;
  currentVal: number;
  currentHour: number;
  clearAll?: boolean;
}

export const ProfileChart: React.FC<ProfileChartProps> = ({
  theme,
  title,
  data,
  color,
  unit,
  yMin,
  yMax,
  currentVal,
  currentHour,
  clearAll = false,
}) => {
  const tokens = THEME_TOKENS[theme];
  const isDarkTheme = theme.startsWith('dark');
  const hasProfile = data.length > 0;
  const sourceData = data.map(([x, y]) => [Number(x), Number(y)] as [number, number]);

  const interpolate = (x: number) => {
    if (x <= sourceData[0][0]) return sourceData[0][1];
    if (x >= sourceData[sourceData.length - 1][0]) return sourceData[sourceData.length - 1][1];
    for (let i = 0; i < sourceData.length - 1; i += 1) {
      const [x1, y1] = sourceData[i];
      const [x2, y2] = sourceData[i + 1];
      if (x >= x1 && x <= x2) {
        const t = (x - x1) / (x2 - x1);
        return y1 + (y2 - y1) * t;
      }
    }
    return sourceData[sourceData.length - 1][1];
  };

  // const denseData: [number, number][] = hasProfile
  //   ? Array.from({ length: 49 }, (_, i) => {
  //       const x = i * 0.5;
  //       const base = interpolate(x);
  //       const wave = title === 'CCT' ? Math.sin(i * 0.35) * 120 : Math.sin(i * 0.45) * 9;
  //       const y = Math.max(yMin, Math.min(yMax, base + wave));
  //       return [x, Number(y.toFixed(2))];
  //     })
  //   : [];

  const denseData: [number, number][] = hasProfile
    ? Array.from({ length: 90 }, (_, i) => {
        const x = i * 0.5;
        const base = interpolate(x);

        const turbulence =
          (Math.sin(i * 0.17) +
            Math.sin(i * 0.043)) * 40;

        const wave =
          title === 'CCT'
            ? Math.sin(i * 0.35) * 90 + turbulence
            : Math.sin(i * 0.45) * 9;

        const y = Math.max(
          yMin,
          Math.min(yMax, base + wave)
        );

        return [x, Number(y.toFixed(2))];
      })
    : [];

  const currentY = hasProfile ? Number(interpolate(currentHour).toFixed(2)) : currentVal;
  const trailingWindow = Math.max(4, Math.floor(denseData.length / 10));
  // const rollingMean: [number, number][] = hasProfile
  //   ? denseData.map((point, idx) => {
  //       const from = Math.max(0, idx - trailingWindow);
  //       const window = denseData.slice(from, idx + 1);
  //       const avg = window.reduce((sum, row) => sum + row[1], 0) / window.length;
  //       return [point[0], Number(avg.toFixed(2))];
  //     })
  //   : [];
  // const trendLine: [number, number][] = hasProfile
  //   ? denseData.map((point, idx) => {
  //       const neighbor = rollingMean[Math.min(rollingMean.length - 1, idx + 2)] ?? rollingMean[idx];
  //       const drift = (neighbor[1] - rollingMean[idx][1]) * 0.85;
  //       const y = Math.max(yMin, Math.min(yMax, rollingMean[idx][1] + drift));
  //       return [point[0], Number(y.toFixed(2))];
  //     })
  //   : [];
  const profileSample = hasProfile ? denseData.filter((_, idx) => idx % 4 === 0) : [];
  const manualTrace: [number, number][] = !hasProfile && !clearAll
    ? Array.from({ length: 25 }, (_, i) => [i, currentVal] as [number, number])
    : [];

  /* =========================
        CCT THERMAL FIELD
  ==========================*/

  const getCCTGradient = (isDark: boolean) =>
    new echarts.graphic.LinearGradient(
      0, 0, 0, 1,
      [
        { offset: 0.0, color: '#2C3E50' },   // Deep Midnight (Top/Strongest)
        { offset: 0.3, color: '#3498DB' },   // Primary Technical Blue
        { offset: 0.6, color: '#AED6F1' },   // Soft Sky Blue
        { offset: 0.85, color: '#D6EAF8CC' }, // Very Pale Crystal
        { 
          offset: 1, 
          color: isDark ? '#1A263500' : '#E6F0FF00' 
        }, // Clean fade to transparent
      ]
    );

  /* =========================
        INTENSITY ENERGY of CCT
  ==========================*/

const getIntensityGradient = () =>
  new echarts.graphic.LinearGradient(
    0, 0, 0, 1,
    [
      { offset: 0, color: '#F39C12EE' },   // Stronger Amber (High Opacity for visibility)
      { offset: 0.4, color: '#F1C40FBB' }, // Solid Sunflower Yellow
      { offset: 1, color: '#F1C40F10' },   // Subtle fade-out
    ]
  );

  const option = {
    animation: true,
    animationDuration: 900,
    title: [
      {
        text: `${title.toUpperCase()} PROFILE`,
        left: 'center',
        top: 8,
        textStyle: {
          fontSize: 14,
          fontWeight: 800,
          color: tokens.textSecondary,
          letterSpacing: 1,
        },
      },
      {
        text: `Current ${title}: ${currentVal.toFixed(1)} ${unit}`,
        right: 10,
        top: 6,
        padding: [7, 12],
        borderRadius: 6,
        backgroundColor: tokens.chartBadgeBg,
        textStyle: {
          color: tokens.chartBadgeText,
          fontSize: 12.5,
          fontWeight: 700,
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: tokens.currentLine, width: 1 } },
      backgroundColor: tokens.cardBgSoft,
      borderColor: tokens.border,
      textStyle: { color: tokens.textPrimary },
      formatter: (params: Array<{ axisValue?: number; seriesName: string; value: [number, number] }>) => {
        const pointLines = params
          .filter((entry) => Array.isArray(entry.value))
          .map((entry) => `${entry.seriesName}: ${Number(entry.value[1]).toFixed(2)} ${unit}`);
        const axisHour =
          typeof params?.[0]?.axisValue === 'number'
            ? params[0].axisValue
            : currentHour;
        const actualValue = hasProfile ? interpolate(axisHour) : currentVal;
        return [
          `Time: ${String(Math.floor(axisHour)).padStart(2, '0')}:${String(Math.round((axisHour % 1) * 60)).padStart(2, '0')}`,
          `Actual: ${Number(actualValue).toFixed(2)} ${unit}`,
          `Current: ${Number(currentVal).toFixed(2)} ${unit}`,
          ...pointLines,
        ].join('<br/>');
      },
    },
    legend: {
      show: !clearAll,
      left: 10,
      top: 36,
      textStyle: { color: tokens.textMuted, fontSize: 10.5 },
      itemWidth: 16,
      itemHeight: 8,
      data: hasProfile ? ['Profile'] : ['Manual Reference'],
    },
    toolbox: {
      right: 10,
      top: 30,
      iconStyle: { borderColor: tokens.textMuted },
      feature: {
        dataZoom: { yAxisIndex: 'none' },
        restore: {},
        saveAsImage: {},
      },
    },
    dataZoom: hasProfile
      ? [
          { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
          {
            type: 'slider',
            height: 14,
            bottom: 12,
            borderColor: tokens.border,
            backgroundColor: tokens.cardBgSoft,
            fillerColor: `${tokens.accentBlue}44`,
          },
        ]
      : [],
    grid: {
      left: 60,
      right: 22,
      bottom: 44,
      top: 74,
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 24,
      interval: 2,
      axisLabel: {
        color: tokens.chartAxis,
        fontSize: 11.5,
        formatter: (value: number) => `${String(Math.floor(value)).padStart(2, '0')}:00`,
      },
      axisLine: { show: false, lineStyle: { color: tokens.chartGrid } },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tokens.chartGrid, width: 1 } },
      minorSplitLine: { show: false, lineStyle: { color: tokens.chartGrid } },
      name: 'Time (Hours)',
      nameLocation: 'middle',
      nameGap: 34,
      nameTextStyle: { color: tokens.textSecondary, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
      interval: title === 'CCT' ? 1000 : 100,
      axisLabel: {
        color: tokens.chartAxis,
        fontSize: 13,
        formatter: (value: number) => value.toLocaleString(),
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tokens.chartGrid, width: 1 } },
      minorSplitLine: { show: true, lineStyle: { color: tokens.chartGrid } },
      name: title === 'CCT' ? 'CCT (K)' : 'Intensity (lux)',
      nameLocation: 'middle',
      nameGap: 48,
      nameTextStyle: { color: tokens.textSecondary, fontSize: 13 },
    },
    series: [
      {
        name: 'Profile',
        data: denseData,
        type: 'line',
        smooth: 0.5,
        showSymbol: hasProfile,
        symbol: 'circle',
        symbolSize: 3,
        lineStyle: { color, width: 2.8, opacity: hasProfile ? 0.95 : 0 },
        areaStyle:
          hasProfile
            ? {
                color:
                  title === 'CCT'
                    ? getCCTGradient(
                        isDarkTheme
                      )
                    : getIntensityGradient(),
                opacity:
                  isDarkTheme
                    ? 0.85
                    : 0.9,
              }
            : undefined,
        markArea:
          hasProfile
            ? {
                silent: true,
                itemStyle: { color: `${tokens.accentBlue}12` },
                data: [[{ xAxis: 8 }, { xAxis: 18 }]],
              }
            : undefined,
        markLine: clearAll
          ? undefined
          : {
          symbol: 'none',
          animation: true,
          lineStyle: { color: tokens.currentLine, width: 2 },
          label: { show: false },
          data: [
            { xAxis: currentHour },
            ...(!hasProfile ? [{ yAxis: currentY }] : []),
          ],
        },
        markPoint:
          clearAll
          ? undefined
          : hasProfile
          ? {
              symbol: 'circle',
              symbolSize: 9,
              data: [{ coord: [currentHour, currentY] }],
              itemStyle: {
                color: tokens.success,
                shadowBlur: 4,
                shadowColor: `${tokens.success}66`,
              },
            }
          : {
              symbol: 'circle',
              symbolSize: 10,
              data: [{ coord: [currentHour, currentY] }],
              itemStyle: {
                color: tokens.success,
                shadowBlur: 8,
                shadowColor: `${tokens.success}66`,
              },
            },
      },
      // {
      //   name: 'Rolling Mean',
      //   type: 'line',
      //   data: rollingMean,
      //   smooth: 0.35,
      //   symbol: 'none',
      //   lineStyle: { color: `${tokens.accentBlue}`, width: 1.4, type: 'dashed', opacity: hasProfile && !clearAll ? 0.72 : 0 },
      //   emphasis: { disabled: true },
      // },
      // {
      //   name: 'Projected',
      //   type: 'line',
      //   data: trendLine,
      //   smooth: 0.25,
      //   symbol: 'none',
      //   lineStyle: { color: `${tokens.accentOrange}`, width: 1.2, type: 'dotted', opacity: hasProfile && !clearAll ? 0.7 : 0 },
      //   emphasis: { disabled: true },
      // },
      // {
      //   name: 'Sample Points',
      //   type: 'scatter',
      //   data: profileSample,
      //   symbolSize: 4,
      //   itemStyle: { color: tokens.textMuted, opacity: hasProfile && !clearAll ? 0.65 : 0 },
      //   emphasis: { disabled: true },
      // },
      {
        name: 'Manual Reference',
        type: 'line',
        data: manualTrace,
        symbol: 'none',
        smooth: false,
        lineStyle: { width: 1, opacity: 0 },
        emphasis: { disabled: true },
      },
    ],
    graphic: clearAll
      ? [
          {
            type: 'text',
            left: 'center',
            top: 'middle',
            style: {
              text: 'System is OFF',
              fill: tokens.textMuted,
              font: '700 14px "SF Pro Display", "Segoe UI", sans-serif',
            },
          },
        ]
      : [],
  };

  return (
    <div className="chart-shell p-2 md:p-3 h-[350px]">
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} opts={{ renderer: 'canvas' }} />
    </div>
  );
};
