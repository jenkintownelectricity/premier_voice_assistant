import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/lib/auth-context'
import { DevModeProvider } from '@/lib/dev-mode-context'
import { DevToolsSidebar } from '@/components/DevToolsSidebar'

export const metadata: Metadata = {
  title: 'HIVE215 - Premier Voice Assistant',
  description: 'Production-ready voice AI system with subscription management',
  icons: {
    icon: '/HIVE215Logo.png',
    apple: '/HIVE215Logo.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-oled-black min-h-screen">
        <AuthProvider>
          <DevModeProvider>
            {children}
            <DevToolsSidebar />
          </DevModeProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
