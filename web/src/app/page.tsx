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

      {/* Hero Section - IVR Killer Positioning */}
      <section className="max-w-7xl mx-auto px-6 py-24 text-center">
        <div className="inline-block px-4 py-2 bg-red-500/10 border border-red-500/30 rounded-full mb-6">
          <span className="text-red-400 text-sm font-semibold">97% of callers hate "Press 1 for Sales"</span>
        </div>
        <h1 className="text-5xl md:text-7xl font-bold">
          <span className="text-white">Fire Your</span>
          <br />
          <span className="text-gold-gradient bg-clip-text text-transparent bg-gradient-to-r from-gold to-gold-shine">
            Robot Receptionist
          </span>
        </h1>
        <p className="mt-6 text-xl text-gray-400 max-w-2xl mx-auto">
          Replace frustrating phone trees with AI that actually <span className="text-white font-semibold">understands</span>.
          Your customers speak naturally. Your AI responds intelligently.
          No more "Press 1, Press 2" forever.
        </p>
        <div className="mt-4 text-amber-400 text-lg font-medium">
          95% cheaper than competitors. Setup in minutes, not weeks.
        </div>
        <div className="mt-10 flex gap-4 justify-center flex-wrap">
          <HoneycombButton size="lg" onClick={() => window.location.href = '/dashboard'}>
            Start Free Trial
          </HoneycombButton>
          <HoneycombButton size="lg" variant="outline" onClick={() => setShowStartupModal(true)}>
            See It In Action
          </HoneycombButton>
        </div>
        <p className="mt-4 text-zinc-500 text-sm">No credit card required. 30 free minutes included.</p>
      </section>

      {/* Problem Statement */}
      <section className="max-w-4xl mx-auto px-6 py-12">
        <div className="bg-zinc-900/50 border border-red-500/20 rounded-xl p-8">
          <h2 className="text-2xl font-bold text-red-400 mb-4">The Problem Everyone Ignores</h2>
          <div className="grid md:grid-cols-3 gap-6 text-center">
            <div>
              <div className="text-4xl font-bold text-red-400">67%</div>
              <div className="text-zinc-400 text-sm">of callers hang up on IVR systems</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-red-400">$5.6B</div>
              <div className="text-zinc-400 text-sm">wasted yearly on outdated phone tech</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-red-400">97%</div>
              <div className="text-zinc-400 text-sm">frustrated with "Press 1" menus</div>
            </div>
          </div>
        </div>
      </section>

      {/* IVR vs HIVE215 Comparison */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gold text-center mb-12">
          Old Phone Tree vs. HIVE215
        </h2>
        <div className="grid md:grid-cols-2 gap-8">
          {/* Old Way */}
          <Card>
            <CardContent>
              <div className="text-red-400 font-bold mb-4">THE OLD WAY</div>
              <div className="space-y-3 text-gray-400">
                <div className="flex items-center gap-2">
                  <span className="text-red-400">✗</span>
                  "Press 1 for Sales, Press 2 for Support..."
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-red-400">✗</span>
                  "Your call is important to us" (10 min hold)
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-red-400">✗</span>
                  "I didn't understand that, let me transfer you"
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-red-400">✗</span>
                  Frustrated customers hang up
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-red-400">✗</span>
                  Lost revenue, poor reviews
                </div>
              </div>
            </CardContent>
          </Card>

          {/* HIVE215 Way */}
          <Card glow>
            <CardContent>
              <div className="text-green-400 font-bold mb-4">THE HIVE215 WAY</div>
              <div className="space-y-3 text-gray-300">
                <div className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  "Hi! How can I help you today?"
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Instant response, no hold music
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  AI understands natural conversation
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Books appointments, captures leads
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  Happy customers, more business
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gold text-center mb-4">
          Everything You Need
        </h2>
        <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
          Built for small businesses who want big-business phone handling without the big-business price tag.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🧠</div>
              <h3 className="text-xl font-bold text-gold mb-2">AI That Understands</h3>
              <p className="text-gray-400 text-sm">
                Powered by Claude - handles complex conversations, not just keywords
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">⚡</div>
              <h3 className="text-xl font-bold text-gold mb-2">Sub-Second Response</h3>
              <p className="text-gray-400 text-sm">
                Real-time voice with under 800ms latency - feels like talking to a human
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-xl font-bold text-gold mb-2">Live Sentiment</h3>
              <p className="text-gray-400 text-sm">
                See caller mood in real-time. Know when to escalate to a human.
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🏆</div>
              <h3 className="text-xl font-bold text-gold mb-2">Quality Scoring</h3>
              <p className="text-gray-400 text-sm">
                Every call gets a quality grade. Track improvement over time.
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">🔧</div>
              <h3 className="text-xl font-bold text-gold mb-2">Industry Templates</h3>
              <p className="text-gray-400 text-sm">
                Pre-built for plumbers, lawyers, restaurants, and more. Setup in 5 minutes.
              </p>
            </CardContent>
          </Card>

          <Card glow>
            <CardContent>
              <div className="text-4xl mb-4">💰</div>
              <h3 className="text-xl font-bold text-gold mb-2">95% Cost Savings</h3>
              <p className="text-gray-400 text-sm">
                Smart caching means you pay a fraction of what competitors charge.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Pricing Preview */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gold text-center mb-4">
          🐝 Simple Pricing
        </h2>
        <p className="text-gray-400 text-center mb-12">Join the hive. Scale with your business.</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card className="hover:border-amber-500/50 transition-colors">
            <CardContent>
              <div className="text-lg font-bold text-gold">The Worker Bee</div>
              <div className="text-3xl font-bold text-white mt-2">$97<span className="text-sm text-gray-400">/mo</span></div>
              <div className="text-gray-400 text-sm mt-2">400 minutes/month</div>
              <div className="text-zinc-500 text-xs mt-1">1 phone number • 1 voice clone</div>
              <HoneycombButton size="sm" variant="outline" className="w-full mt-4" onClick={() => window.location.href = '/dashboard'}>
                Start Trial
              </HoneycombButton>
            </CardContent>
          </Card>

          <Card glow className="border-amber-500/50">
            <CardContent>
              <div className="text-xs text-amber-400 font-semibold mb-1">🔥 MOST POPULAR</div>
              <div className="text-lg font-bold text-gold">The Swarm</div>
              <div className="text-3xl font-bold text-white mt-2">$297<span className="text-sm text-gray-400">/mo</span></div>
              <div className="text-gray-400 text-sm mt-2">1,350 minutes/month</div>
              <div className="text-zinc-500 text-xs mt-1">3 phone numbers • 3 voice clones</div>
              <HoneycombButton size="sm" className="w-full mt-4" onClick={() => window.location.href = '/dashboard'}>
                Get Started
              </HoneycombButton>
            </CardContent>
          </Card>

          <Card className="hover:border-amber-500/50 transition-colors">
            <CardContent>
              <div className="text-lg font-bold text-gold">The Queen Bee</div>
              <div className="text-3xl font-bold text-white mt-2">$697<span className="text-sm text-gray-400">/mo</span></div>
              <div className="text-gray-400 text-sm mt-2">3,500 minutes/month</div>
              <div className="text-zinc-500 text-xs mt-1">10 phone numbers • 10 voice clones</div>
              <HoneycombButton size="sm" variant="outline" className="w-full mt-4" onClick={() => window.location.href = '/dashboard'}>
                Go Big
              </HoneycombButton>
            </CardContent>
          </Card>

          <Card className="hover:border-amber-500/50 transition-colors">
            <CardContent>
              <div className="text-lg font-bold text-gold">The Hive Mind</div>
              <div className="text-3xl font-bold text-white mt-2">Custom</div>
              <div className="text-gray-400 text-sm mt-2">10,000+ minutes/month</div>
              <div className="text-zinc-500 text-xs mt-1">White label • Dedicated rep</div>
              <HoneycombButton size="sm" variant="outline" className="w-full mt-4" onClick={() => window.location.href = 'mailto:sales@hive215.com?subject=The%20Hive%20Mind%20Inquiry'}>
                Contact Us
              </HoneycombButton>
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
