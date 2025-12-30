'use client';

import { clsx } from 'clsx';

interface HoneycombButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'solid' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

export function HoneycombButton({
  children,
  onClick,
  variant = 'solid',
  size = 'md',
  disabled = false,
  className = '',
  type = 'button',
}: HoneycombButtonProps) {
  const sizeClasses = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base',
    lg: 'px-8 py-4 text-lg',
  };

  const baseClasses = clsx(
    'relative font-semibold transition-all duration-300 inline-flex items-center justify-center',
    sizeClasses[size],
    disabled && 'opacity-50 cursor-not-allowed',
    className
  );

  if (variant === 'outline') {
    return (
      <button
        type={type}
        onClick={onClick}
        disabled={disabled}
        className={clsx(
          baseClasses,
          'text-gold border-2 border-gold bg-transparent hover:bg-gold hover:text-black hover:shadow-gold'
        )}
        style={{
          clipPath: 'polygon(10% 0%, 90% 0%, 100% 50%, 90% 100%, 10% 100%, 0% 50%)',
        }}
      >
        {children}
      </button>
    );
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        baseClasses,
        'text-black hover:shadow-gold-lg hover:scale-105 active:scale-95'
      )}
      style={{
        background: 'linear-gradient(135deg, #D4AF37 0%, #FFD700 50%, #B8860B 100%)',
        clipPath: 'polygon(10% 0%, 90% 0%, 100% 50%, 90% 100%, 10% 100%, 0% 50%)',
      }}
    >
      {children}
    </button>
  );
}
