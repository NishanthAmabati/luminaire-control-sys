import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface CardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  headerClassName?: string;
  icon?: LucideIcon;
  headerAction?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  title,
  children,
  className = '',
  contentClassName = '',
  headerClassName = '',
  icon: Icon,
  headerAction,
}) => (
  <section className={`panel h-full flex flex-col overflow-hidden ${className}`}>
    <header className={`panel-header flex items-center justify-between gap-2 ${headerClassName}`}>
      <h3 className="panel-title">
        {Icon ? <Icon size={30} className="panel-title-icon" /> : null}
        {title}
      </h3>
      {headerAction}
    </header>
    <div className={`panel-content flex-1 flex flex-col ${contentClassName}`}>{children}</div>
  </section>
);
