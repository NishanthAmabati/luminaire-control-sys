import React from 'react';
import ReactECharts from 'echarts-for-react';
import { THEME_TOKENS } from '../../../config/theme.tokens';
import type { DashboardTheme } from '../../../types/theme';
import * as echarts from 'echarts';

interface DualProfileChartProps {
  theme: DashboardTheme;
  cctData: [number, number][];
  cctColor: string;
  cctUnit: string;
  cctMin: number;
  cctMax: number;
  currentCct: number;
  intensityData: [number, number][];
  intensityColor: string;
  intensityUnit: string;
  intensityMin: number;
  intensityMax: number;
  currentLux: number;
  currentHour: number;
  clearAll?: boolean;
}

const parseSeries = (raw: [number, number][]) => raw.map(([x, y]) => [Number(x), Number(y)] as [number, number]);

const interpolate = (data: [number, number][], x: number, fallback: number) => {
  if (data.length === 0) return fallback;
  if (x <= data[0][0]) return data[0][1];
  if (x >= data[data.length - 1][0]) return data[data.length - 1][1];
  for (let i = 0; i < data.length - 1; i += 1) {
    const [x1, y1] = data[i];
    const [x2, y2] = data[i + 1];
    if (x >= x1 && x <= x2) {
      const t = (x - x1) / (x2 - x1);
      return y1 + (y2 - y1) * t;
    }
  }
  return data[data.length - 1][1];
};

const makeDense = (
  data: [number, number][],
  yMin: number,
  yMax: number,
  isCct: boolean,
  fallback: number,
): [number, number][] => {
  const has = data.length > 0;
  if (!has) return [];
  return Array.from({ length: 60 }, (_, i) => {
    const x = i * 0.5;
    const base = interpolate(data, x, fallback);
    const turbulence = (Math.sin(i * 0.17) + Math.sin(i * 0.043)) * 40;
    const wave = isCct
      ? Math.sin(i * 0.35) * 90 + turbulence
      : Math.sin(i * 0.45) * 9;
    const y = Math.max(yMin, Math.min(yMax, base + wave));
    return [x, Number(y.toFixed(2))] as [number, number];
  });
};

export const DualProfileChart: React.FC<DualProfileChartProps> = ({
  theme,
  cctData,
  cctColor,
  cctUnit,
  cctMin,
  cctMax,
  currentCct,
  intensityData,
  intensityColor,
  intensityUnit,
  intensityMin,
  intensityMax,
  currentLux,
  currentHour,
  clearAll = false,
}) => {
  const tokens = THEME_TOKENS[theme];
  const hasCct = cctData.length > 0;
  const hasIntensity = intensityData.length > 0;
  const srcCct = parseSeries(cctData);
  const srcInt = parseSeries(intensityData);

  const denseCct = makeDense(srcCct, cctMin, cctMax, true, currentCct);
  const denseInt = makeDense(srcInt, intensityMin, intensityMax, false, currentLux);

  const dotPosCct = (() => {
    if (!hasCct || denseCct.length === 0) return { x: currentHour, y: currentCct };
    const idx = Math.round(currentHour * 2);
    const ci = Math.max(0, Math.min(denseCct.length - 1, idx));
    return { x: ci * 0.5, y: denseCct[ci][1] };
  })();
  const dotPosInt = (() => {
    if (!hasIntensity || denseInt.length === 0) return { x: currentHour, y: currentLux };
    const idx = Math.round(currentHour * 2);
    const ci = Math.max(0, Math.min(denseInt.length - 1, idx));
    return { x: ci * 0.5, y: denseInt[ci][1] };
  })();

  const manualCct: [number, number][] = !hasCct && !clearAll
    ? Array.from({ length: 25 }, (_, i) => [i, currentCct] as [number, number])
    : [];
  const manualInt: [number, number][] = !hasIntensity && !clearAll
    ? Array.from({ length: 25 }, (_, i) => [i, currentLux] as [number, number])
    : [];

  const cctGrad = () => {
    const g = tokens.chartGradients.cct;
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: g[0] },
      { offset: 0.3, color: g[1] },
      { offset: 0.6, color: g[2] },
      { offset: 0.85, color: g[3] },
      { offset: 1, color: g[4] + '00' },
    ]);
  };

  const intGrad = () => {
    const g = tokens.chartGradients.intensity;
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: g[0] },
      { offset: 0.4, color: g[1] },
      { offset: 1, color: g[2] },
    ]);
  };

  const option = {
    animation: true,
    animationDuration: 150,
    animationEasing: 'cubicOut' as const,
    title: [
      {
        text: 'CCT & INTENSITY PROFILE',
        left: 8,
        top: 4,
        textStyle: {
          fontSize: 10,
          fontWeight: 800,
          color: tokens.textSecondary,
          letterSpacing: 1,
        },
      },
      {
        text: `CCT: ${currentCct.toFixed(0)}${cctUnit}  |  INT: ${currentLux.toFixed(0)}${intensityUnit}`,
        right: 6,
        top: 20,
        padding: [3, 6],
        borderRadius: 4,
        backgroundColor: tokens.chartBadgeBg,
        textStyle: {
          color: tokens.chartBadgeText,
          fontSize: 9,
          fontWeight: 700,
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: tokens.currentLine, width: 1 },
      },
      backgroundColor: tokens.cardBgSoft,
      borderColor: tokens.border,
      textStyle: { color: tokens.textPrimary, fontSize: 10 },
      formatter: (params: Array<{ axisValue?: number; seriesName: string; value: [number, number] }>) => {
        const t = typeof params?.[0]?.axisValue === 'number' ? params[0].axisValue : currentHour;
        const lines = params
          .filter((p) => Array.isArray(p.value))
          .map((p) => `${p.seriesName}: ${Number(p.value[1]).toFixed(0)}`);
        const actualCct = hasCct ? interpolate(srcCct, t, currentCct) : currentCct;
        const actualLux = hasIntensity ? interpolate(srcInt, t, currentLux) : currentLux;
        return [
          `<b>${String(Math.floor(t)).padStart(2, '0')}:${String(Math.round((t % 1) * 60)).padStart(2, '0')}</b>`,
          `Actual CCT: ${actualCct.toFixed(0)}${cctUnit}`,
          `Actual INT: ${actualLux.toFixed(0)}${intensityUnit}`,
          ...lines,
        ].join('<br/>');
      },
    },
    legend: {
      show: !clearAll,
      left: 8,
      top: 28,
      textStyle: { color: tokens.textMuted, fontSize: 9 },
      itemWidth: 12,
      itemHeight: 6,
      data: [
        ...(hasCct ? [{ name: 'CCT Profile', icon: 'roundRect' }] : []),
        ...(hasIntensity ? [{ name: 'Intensity Profile', icon: 'roundRect' }] : []),
      ],
    },
    grid: {
      left: 44,
      right: 44,
      bottom: 30,
      top: 58,
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 24,
      interval: 4,
      axisLabel: {
        color: tokens.chartAxis,
        fontSize: 9,
        formatter: (value: number) => `${String(Math.floor(value)).padStart(2, '0')}:00`,
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: tokens.chartGrid, width: 1 } },
    },
    yAxis: [
      {
        type: 'value',
        min: cctMin,
        max: cctMax,
        splitNumber: 3,
        axisLabel: {
          color: tokens.chartAxis,
          fontSize: 9,
          formatter: (v: number) => v.toLocaleString(),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: tokens.chartGrid, width: 1 } },
        name: 'CCT (K)',
        nameLocation: 'middle',
        nameGap: 34,
        nameTextStyle: { color: tokens.textSecondary, fontSize: 9 },
      },
      {
        type: 'value',
        min: intensityMin,
        max: intensityMax,
        splitNumber: 3,
        axisLabel: {
          color: tokens.chartAxis,
          fontSize: 9,
          formatter: (v: number) => v.toLocaleString(),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        name: 'Intensity (lux)',
        nameLocation: 'middle',
        nameGap: 36,
        nameTextStyle: { color: tokens.textSecondary, fontSize: 9 },
      },
    ],
    series: [
      {
        name: 'CCT Profile',
        yAxisIndex: 0,
        data: denseCct,
        type: 'line',
        smooth: 0.5,
        showSymbol: false,
        lineStyle: { color: cctColor, width: 2, opacity: hasCct ? 0.95 : 0 },
        areaStyle: hasCct ? { color: cctGrad(), opacity: 0.75 } : undefined,
        markArea: hasCct ? {
          silent: true,
          itemStyle: { color: `${tokens.accentBlue}12` },
          data: [[{ xAxis: 8 }, { xAxis: 18 }]],
        } : undefined,
        markLine: {
          symbol: ['none', 'none'],
          animation: true,
          animationDuration: 150,
          animationEasing: 'cubicOut' as const,
          lineStyle: { color: hasCct ? tokens.currentLine : tokens.textMuted, width: hasCct ? 1.5 : 1, type: hasCct ? 'solid' : 'dashed' },
          label: { show: false },
          data: [
            { xAxis: dotPosCct.x },
            ...(!hasCct ? [{ yAxis: dotPosCct.y }] : []),
          ],
        },
      },
      {
        name: 'CCT Dot',
        yAxisIndex: 0,
        type: 'scatter',
        data: hasCct && !clearAll ? [[dotPosCct.x, dotPosCct.y]] : [],
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: tokens.success, shadowBlur: 6, shadowColor: tokens.success },
        z: 10,
      },
      {
        name: 'CCT Manual',
        yAxisIndex: 0,
        type: 'line',
        data: manualCct,
        symbol: 'none',
        smooth: false,
        lineStyle: { width: 1, opacity: 0 },
        emphasis: { disabled: true },
      },
      {
        name: 'Intensity Profile',
        yAxisIndex: 1,
        data: denseInt,
        type: 'line',
        smooth: 0.5,
        showSymbol: false,
        lineStyle: { color: intensityColor, width: 2, opacity: hasIntensity ? 0.95 : 0 },
        areaStyle: hasIntensity ? { color: intGrad(), opacity: 0.75 } : undefined,
        markLine: {
          symbol: ['none', 'none'],
          animation: true,
          animationDuration: 150,
          animationEasing: 'cubicOut' as const,
          lineStyle: { color: hasIntensity ? tokens.currentLine : tokens.textMuted, width: hasIntensity ? 1.5 : 1, type: hasIntensity ? 'solid' : 'dashed' },
          label: { show: false },
          data: [
            { xAxis: dotPosInt.x },
            ...(!hasIntensity ? [{ yAxis: dotPosInt.y }] : []),
          ],
        },
      },
      {
        name: 'Intensity Dot',
        yAxisIndex: 1,
        type: 'scatter',
        data: hasIntensity && !clearAll ? [[dotPosInt.x, dotPosInt.y]] : [],
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: intensityColor, shadowBlur: 6, shadowColor: intensityColor },
        z: 10,
      },
      {
        name: 'Intensity Manual',
        yAxisIndex: 1,
        type: 'line',
        data: manualInt,
        symbol: 'none',
        smooth: false,
        lineStyle: { width: 1, opacity: 0 },
        emphasis: { disabled: true },
      },
    ],
  };

  return (
    <div className="dual-chart-shell">
      <ReactECharts
        option={option}
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'canvas' }}
        lazyUpdate={false}
      />
    </div>
  );
};
