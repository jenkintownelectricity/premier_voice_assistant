'use client';

import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface HipaaBadgeProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function HipaaBadge({ size = 'md', className = '' }: HipaaBadgeProps) {
  const sizeClasses = {
    sm: {
      container: 'px-2 py-1',
      icon: 'w-3 h-3',
      title: 'text-[8px]',
      subtitle: 'text-[7px]',
    },
    md: {
      container: 'px-3 py-1.5',
      icon: 'w-4 h-4',
      title: 'text-[10px]',
      subtitle: 'text-[9px]',
    },
    lg: {
      container: 'px-4 py-2',
      icon: 'w-5 h-5',
      title: 'text-xs',
      subtitle: 'text-[10px]',
    },
  };

  const classes = sizeClasses[size];

  return (
    <div
      className={`flex items-center gap-2 ${classes.container} bg-blue-900/20 border border-blue-800 rounded-full w-fit ${className}`}
    >
      <ShieldCheck className={`${classes.icon} text-blue-400`} />
      <div className="flex flex-col">
        <span
          className={`${classes.title} uppercase font-bold text-blue-300 tracking-wider leading-none`}
        >
          HIPAA Compliant
        </span>
        <span className={`${classes.subtitle} text-blue-400/60 leading-none`}>
          256-bit AES Encryption
        </span>
      </div>
    </div>
  );
}
