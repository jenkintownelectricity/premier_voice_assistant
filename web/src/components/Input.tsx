'use client';

import { clsx } from 'clsx';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-gold mb-2">
          {label}
        </label>
      )}
      <input
        className={clsx(
          'w-full px-4 py-3 bg-oled-gray border border-gold/30 rounded-lg',
          'text-white placeholder-gray-500',
          'focus:outline-none focus:border-gold focus:ring-1 focus:ring-gold/50',
          'transition-all duration-200',
          error && 'border-red-500 focus:border-red-500 focus:ring-red-500/50',
          className
        )}
        {...props}
      />
      {error && (
        <p className="mt-1 text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, error, options, className = '', ...props }: SelectProps) {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-gold mb-2">
          {label}
        </label>
      )}
      <select
        className={clsx(
          'w-full px-4 py-3 bg-oled-gray border border-gold/30 rounded-lg',
          'text-white',
          'focus:outline-none focus:border-gold focus:ring-1 focus:ring-gold/50',
          'transition-all duration-200',
          error && 'border-red-500 focus:border-red-500 focus:ring-red-500/50',
          className
        )}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-1 text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}
