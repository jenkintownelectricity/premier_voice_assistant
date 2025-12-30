'use client';

import { clsx } from 'clsx';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  honeycomb?: boolean;
  glow?: boolean;
}

export function Card({ children, className = '', honeycomb = true, glow = false }: CardProps) {
  return (
    <div
      className={clsx(
        'relative bg-oled-surface border border-gold/20 rounded-lg overflow-hidden p-6',
        honeycomb && 'bg-honeycomb',
        glow && 'border-gold-glow shadow-gold',
        className
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return (
    <div className={clsx('mb-4', className)}>
      {children}
    </div>
  );
}

interface CardTitleProps {
  children: React.ReactNode;
  className?: string;
}

export function CardTitle({ children, className = '' }: CardTitleProps) {
  return (
    <h3 className={clsx('text-lg font-semibold text-gold', className)}>
      {children}
    </h3>
  );
}

interface CardContentProps {
  children: React.ReactNode;
  className?: string;
}

export function CardContent({ children, className = '' }: CardContentProps) {
  return (
    <div className={clsx('text-gray-300', className)}>
      {children}
    </div>
  );
}
