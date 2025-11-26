'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Card, CardContent } from '@/components/Card';
import { StartupModal } from '@/components/StartupModal';

export default function HomePage() {
  const [showStartupModal, setShowStartupModal] = useState(false);

  // Show modal on startup (only once per session)
  useEffect(() => {
    const hasSeenModal = sessionStorage.getItem('hive215_startup_modal_seen');
    if (!hasSeenModal) {
      setShowStartupModal(true);
    }
  }, []);

  const handleCloseModal = () => {
    setShowStartupModal(false);
    sessionStorage.setItem('hive215_startup_modal_seen', 'true');
  };

  return (
    <div className="min-h-screen bg-oled-black bg-honeycomb">
      {/* Startup Modal */}
      {showStartupModal && <StartupModal onClose={handleCloseModal} />}

      {/* Header */}
      <header className="border-b border-gold/20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <Image
              src="/HIVE215Logo.png"
              alt="HIVE215 Logo"
              width={40}
              height={40}
              className="rounded"
            />
            <span className="text-xl font-bold text-gold">HIVE215</span>
          </div>

          <nav className="flex items-center gap-6">
            <a href="/dashboard" className="text-gray-400 hover:text-gold transition-colors">
              Dashboard
            </a>
            <a href="/admin" className="text-gray-400 hover:text-gold transition-colors">
              Admin
            </a>
            <HoneycombButton size="sm" variant="outline" onClick={() => setShowStartupModal(true)}>
              Ask AI
            </HoneycombButton>
            <HoneycombButton size="sm" onClick={() => window.location.href = '/dashboard'}>
              Get Started
            </HoneycombButton>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 py-24 text-center">
        <h1 className="text-5xl md:text-7xl font-bold">
          <span className="text-white">Voice AI for</span>
          <br />
          <span className="text-gold-gradient bg-clip-text text-transparent bg-gradient-to-r from-gold to-gold-shine">
            Your Business
          </span>
        </h1>
        <p className="mt-6 text-xl text-gray-400 max-w-2xl mx-auto">
          Production-ready voice assistant with subscription management,
          usage tracking, and enterprise-grade reliability.
        </p>
        <div className="mt-10 flex gap-4 justify-center">
          <HoneycombButton size="lg" onClick={() => window.location.href = '/dashboard'}>
            View Dashboard
          </HoneycombButton>
          <HoneycombButton size="lg" variant="outline" onClick={() => window.location.href = '/admin'}>
            Admin Panel
          </HoneycombButton>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gold text-center mb-12">
          Platform Features
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🎙️</div>
              <h3 className="text-xl font-bold text-gold mb-2">Voice Pipeline</h3>
              <p className="text-gray-400 text-sm">
                Whisper STT → Claude LLM → Coqui TTS with sub-second latency
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">💳</div>
              <h3 className="text-xl font-bold text-gold mb-2">Subscriptions</h3>
              <p className="text-gray-400 text-sm">
                Stripe integration with automatic billing and usage enforcement
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-xl font-bold text-gold mb-2">Analytics</h3>
              <p className="text-gray-400 text-sm">
                Real-time usage tracking, revenue metrics, and user insights
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🎁</div>
              <h3 className="text-xl font-bold text-gold mb-2">Discount Codes</h3>
              <p className="text-gray-400 text-sm">
                Flexible promotional system with bonus minutes and upgrades
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🔊</div>
              <h3 className="text-xl font-bold text-gold mb-2">Voice Cloning</h3>
              <p className="text-gray-400 text-sm">
                Custom voice creation with Coqui XTTS-v2 technology
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">📱</div>
              <h3 className="text-xl font-bold text-gold mb-2">Mobile Ready</h3>
              <p className="text-gray-400 text-sm">
                Client-safe APIs for iOS, Android, and web integration
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Pricing Preview */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gold text-center mb-12">
          Simple Pricing
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent>
              <div className="text-lg font-bold text-gold">Free</div>
              <div className="text-3xl font-bold text-white mt-2">$0</div>
              <div className="text-gray-400 text-sm mt-2">100 minutes/month</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <div className="text-lg font-bold text-gold">Starter</div>
              <div className="text-3xl font-bold text-white mt-2">$99</div>
              <div className="text-gray-400 text-sm mt-2">2,000 minutes/month</div>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-xs text-gold font-semibold mb-1">POPULAR</div>
              <div className="text-lg font-bold text-gold">Pro</div>
              <div className="text-3xl font-bold text-white mt-2">$299</div>
              <div className="text-gray-400 text-sm mt-2">10,000 minutes/month</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <div className="text-lg font-bold text-gold">Enterprise</div>
              <div className="text-3xl font-bold text-white mt-2">Custom</div>
              <div className="text-gray-400 text-sm mt-2">Unlimited minutes</div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gold/20 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 text-center text-gray-500 text-sm">
          © 2024 HIVE215 - Premier Voice Assistant. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
