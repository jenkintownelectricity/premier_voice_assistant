'use client';

import { createContext, useContext } from 'react';

// Admin context for sharing admin key
interface AdminContextType {
  adminKey: string;
  setAdminKey: (key: string) => void;
}

export const AdminContext = createContext<AdminContextType | undefined>(undefined);

export function useAdmin() {
  const context = useContext(AdminContext);
  if (!context) {
    throw new Error('useAdmin must be used within AdminLayout');
  }
  return context;
}
