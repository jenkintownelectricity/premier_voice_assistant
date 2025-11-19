import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Premier Voice Assistant',
  description: 'Production-ready voice AI system with subscription management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-oled-black min-h-screen">
        {children}
      </body>
    </html>
  )
}
