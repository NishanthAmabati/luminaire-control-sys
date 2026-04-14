import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface StatItemProps {
  label: string;
  value: string | number;
  unit: string;
  icon: LucideIcon;
}

export const StatItem: React.FC<StatItemProps> = ({ label, value, unit, icon: Icon }) => (
  <div className="metric-chip motion-soft flex items-center gap-3 px-3 py-2">
    <Icon size={40} style={{ color: 'var(--stat-icon-color)' }} />
    <div>
      <p className="text-caption font-semibold uppercase tracking-wide">
        {label}
      </p>
      <div className="flex items-baseline gap-1">
        <span className="text-lg font-extrabold" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
        <span className="text-caption font-bold" style={{ color: 'var(--text-secondary)' }}>
          {unit}
        </span>
      </div>
    </div>
  </div>
);
