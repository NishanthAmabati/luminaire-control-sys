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
    <Icon size={40} style={{ color: 'var(--text-secondary)' }} />
    <div>
      <p className="text-[0.72rem] font-semibold uppercase tracking-wide data-text" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      <div className="flex items-baseline gap-1">
        <span className="text-[1rem] font-extrabold data-text" style={{ color: 'var(--text-primary)' }}>
          {value}
        </span>
        <span className="text-[0.72rem] font-bold data-text" style={{ color: 'var(--text-secondary)' }}>
          {unit}
        </span>
      </div>
    </div>
  </div>
);
