'use client';

import { useState, useEffect } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Card, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input } from '@/components/Input';
import { AdminContext } from '@/lib/admin-context';

// SVG icons for navigation
const DashboardIcon = () => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
  </svg>
);

const UsersIcon = () => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
  </svg>
);

const CodesIcon = () => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
  </svg>
);

const ChartIcon = () => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
);

const BackIcon = () => (
  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
  </svg>
);

const navItems = [
  { name: 'Dashboard', href: '/admin', icon: <DashboardIcon /> },
  { name: 'Users', href: '/admin/users', icon: <UsersIcon /> },
  { name: 'Discount Codes', href: '/admin/codes', icon: <CodesIcon /> },
  { name: 'Analytics', href: '/admin/analytics', icon: <ChartIcon /> },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [adminKey, setAdminKey] = useState('');
  const [tempKey, setTempKey] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // Check for stored admin key
    const stored = localStorage.getItem('admin_key');
    if (stored) {
      setAdminKey(stored);
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = () => {
    if (tempKey.trim()) {
      localStorage.setItem('admin_key', tempKey);
      setAdminKey(tempKey);
      setIsAuthenticated(true);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_key');
    setAdminKey('');
    setIsAuthenticated(false);
    setTempKey('');
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-oled-black bg-honeycomb flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gold">Admin Access</h1>
            <p className="text-gray-400 mt-2">Enter your admin API key to continue</p>
          </div>
          <Card glow>
            <CardContent>
              <div className="space-y-4">
                <Input
                  label="Admin API Key"
                  type="password"
                  value={tempKey}
                  onChange={(e) => setTempKey(e.target.value)}
                  placeholder="Enter your admin key..."
                />
                <HoneycombButton onClick={handleLogin} className="w-full">
                  Access Admin Panel
                </HoneycombButton>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <AdminContext.Provider value={{ adminKey, setAdminKey }}>
      <div className="flex min-h-screen bg-oled-black bg-honeycomb">
        <Sidebar
          items={navItems}
          title="Admin"
          bottomItems={[
            { name: 'Back to Dashboard', href: '/dashboard', icon: <BackIcon /> },
            { name: 'Logout Admin', href: '#', icon: <BackIcon />, onClick: handleLogout },
          ]}
        />
        <main className="flex-1 p-8">
          {children}
        </main>
      </div>
    </AdminContext.Provider>
  );
}
