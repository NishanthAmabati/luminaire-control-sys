// src/components/StatCard.tsx
import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  unit: string;
}

export const StatCard: React.FC<StatCardProps> = ({ icon: Icon, label, value, unit }) => (
  <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
    <div className="p-2 bg-white rounded-md shadow-sm">
      <Icon size={18} className="text-gray-600" />
    </div>
    <div>
      <p className="text-[10px] text-gray-400 font-bold uppercase">{label}</p>
      <p className="text-sm font-bold text-gray-800">{value}{unit}</p>
    </div>
  </div>
);
