import React from 'react';
import { Activity, Cpu, MemoryStick, Thermometer } from 'lucide-react';

interface StatsPillsProps {
  latency: string | number;
  cpu: string | number;
  memory: string | number;
  temperature: string | number;
}

export const StatsPills: React.FC<StatsPillsProps> = ({ latency, cpu, memory, temperature }) => (
  <div className="stats-pills">
    <span className="pill-item">
      <Activity size={11} strokeWidth={2.5} />
      <span className="pill-val">{latency}</span>
      <span className="pill-unit">ms</span>
    </span>
    <span className="pill-item">
      <Cpu size={11} strokeWidth={2.5} />
      <span className="pill-val">{cpu}</span>
      <span className="pill-unit">%</span>
    </span>
    <span className="pill-item">
      <MemoryStick size={11} strokeWidth={2.5} />
      <span className="pill-val">{memory}</span>
      <span className="pill-unit">%</span>
    </span>
    <span className="pill-item">
      <Thermometer size={11} strokeWidth={2.5} />
      <span className="pill-val">{temperature}</span>
      <span className="pill-unit">°C</span>
    </span>
  </div>
);
