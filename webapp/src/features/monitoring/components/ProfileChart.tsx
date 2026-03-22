import React, { useEffect, useState, startTransition } from 'react';
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
  const hasProfile = data.length > 0;
  const sourceData = data.map(([x, y]) => [Number(x), Number(y)] as [number, number]);
  const [needsEntryAnimation, setNeedsEntryAnimation] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setNeedsEntryAnimation(false), 400);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    startTransition(() => {
      setNeedsEntryAnimation(true);
    });
    const timer = setTimeout(() => setNeedsEntryAnimation(false), 400);
    return () => clearTimeout(timer);
  }, [hasProfile]);

  const interpolate = (x: number) => {
    if (sourceData.length === 0) return currentVal;
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

  const getWavyYAt = (hour: number): number => {
    if (!hasProfile || denseData.length === 0) return currentVal;
    const idx = Math.round(hour * 2);
    const clampedIdx = Math.max(0, Math.min(denseData.length - 1, idx));
    return denseData[clampedIdx][1];
  };

  const currentY = hasProfile ? getWavyYAt(currentHour) : currentVal;
  const manualTrace: [number, number][] = !hasProfile && !clearAll
    ? Array.from({ length: 25 }, (_, i) => [i, currentVal] as [number, number])
    : [];

  const getCCTGradient = () => {
    const gradient = tokens.chartGradients.cct;
    return new echarts.graphic.LinearGradient(
      0, 0, 0, 1,
      [
        { offset: 0.0, color: gradient[0] },
        { offset: 0.3, color: gradient[1] },
        { offset: 0.6, color: gradient[2] },
        { offset: 0.85, color: gradient[3] },
        { offset: 1, color: gradient[4] + '00' },
      ]
    );
  };

  const getIntensityGradient = () => {
    const gradient = tokens.chartGradients.intensity;
    return new echarts.graphic.LinearGradient(
      0, 0, 0, 1,
      [
        { offset: 0, color: gradient[0] },
        { offset: 0.4, color: gradient[1] },
        { offset: 1, color: gradient[2] },
      ]
    );
  };

  const option = {
    animation: true,
    animationDuration: 150,
    animationEasing: 'cubicOut' as const,
    title: [
      {
        text: `${title.toUpperCase()} ${hasProfile ? 'PROFILE' : 'TRACE'}`,
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
                    ? getCCTGradient()
                    : getIntensityGradient(),
                opacity: 0.85,
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
            animationDuration: 150,
            animationEasing: 'cubicOut' as const,
            lineStyle: {
              color: hasProfile ? tokens.currentLine : tokens.textMuted,
              width: hasProfile ? 2 : 1.5,
              type: hasProfile ? 'solid' : 'dashed',
            },
            label: { show: false },
            data: [
              { xAxis: currentHour },
              ...(!hasProfile ? [{ yAxis: currentY }] : []),
            ],
          },
        markPoint: !hasProfile && !clearAll
          ? {
              symbol: 'triangle',
              symbolSize: 14,
              symbolRotate: 0,
              data: [{ coord: [currentHour, currentY] }],
              itemStyle: {
                color: color,
              },
              animation: true,
              animationDuration: 100,
              animationDelay: 50,
              animationEasing: 'cubicOut' as const,
            }
          : hasProfile && !clearAll
          ? {
              symbol: 'circle',
              symbolSize: 8,
              data: [{ coord: [currentHour, currentY] }],
              itemStyle: {
                color: tokens.success,
              },
              animation: true,
              animationDuration: 100,
              animationDelay: 50,
              animationEasing: 'cubicOut' as const,
            }
          : undefined,
      },
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
      ? []
      : [],
  };

  return (  
    <div className={`chart-shell p-2 md:p-3 h-[350px] ${needsEntryAnimation ? 'entering' : ''}`}>
      <ReactECharts 
        option={option} 
        style={{ height: '100%', width: '100%' }} 
        opts={{ renderer: 'canvas' }}
        lazyUpdate={false}
      />
    </div>
  );
};
