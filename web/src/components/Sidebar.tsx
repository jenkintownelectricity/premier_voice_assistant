'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clsx } from 'clsx';

interface NavItem {
  name: string;
  href: string;
  icon: React.ReactNode;
}

interface SidebarProps {
  items: NavItem[];
  title?: string;
}

export function Sidebar({ items, title = 'HIVE215' }: SidebarProps) {
  const pathname = usePathname();

  return (
    <div className="w-64 bg-oled-dark border-r border-gold/20 min-h-screen flex flex-col">
      {/* Logo area */}
      <div className="p-6 border-b border-gold/20">
        <div className="flex items-center gap-3">
          <Image
            src="/HIVE215Logo.png"
            alt="HIVE215 Logo"
            width={40}
            height={40}
            className="rounded"
          />
          <span className="text-lg font-bold text-gold-gradient bg-clip-text text-transparent bg-gradient-to-r from-gold to-gold-shine">
            {title}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {items.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                isActive
                  ? 'bg-gold/20 text-gold border border-gold/30'
                  : 'text-gray-400 hover:text-gold hover:bg-gold/10'
              )}
            >
              <span className={clsx('w-5 h-5', isActive && 'text-gold')}>
                {item.icon}
              </span>
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gold/20">
        <div className="text-xs text-gray-500 text-center">
          HIVE215 v0.2.0
        </div>
      </div>
    </div>
  );
}
