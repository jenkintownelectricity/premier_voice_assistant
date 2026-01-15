'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function EarlyRisersLanding() {
  const router = useRouter();
  const [email, setEmail] = useState('');

  const handleJoin = () => {
    router.push(`/signup?contest=early_risers_2026${email ? `&email=${encodeURIComponent(email)}` : ''}`);
  };

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-gold/20 via-transparent to-orange-500/10" />
        <div className="max-w-6xl mx-auto px-6 py-20 relative z-10">
          <div className="text-center">
            <div className="inline-block px-4 py-2 bg-gold/20 text-gold rounded-full text-sm font-medium mb-6">
              LIMITED TIME OFFER
            </div>
            <h1 className="text-5xl md:text-7xl font-bold mb-6">
              <span className="text-gold">EARLY RISERS</span>
              <br />
              <span className="text-white">CONTEST</span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 mb-8 max-w-2xl mx-auto">
              Get <span className="text-gold font-bold">90 days FREE</span> premium access to HIVE215 Voice AI Platform.
              No credit card required.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center max-w-md mx-auto">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="w-full sm:flex-1 px-6 py-4 bg-white/10 border border-gold/30 rounded-lg text-white placeholder-gray-400 focus:border-gold focus:outline-none"
              />
              <button
                onClick={handleJoin}
                className="w-full sm:w-auto px-8 py-4 bg-gold text-black font-bold rounded-lg hover:bg-gold/90 transition-colors"
              >
                JOIN NOW
              </button>
            </div>

            <p className="text-gray-500 text-sm mt-4">
              Available while funding lasts. No strings attached.
            </p>
          </div>
        </div>
      </div>

      {/* What You Get */}
      <div className="bg-gray-900/50 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">What You Get</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-black/50 border border-gray-800 rounded-xl p-8 text-center">
              <div className="text-5xl mb-4">90</div>
              <div className="text-gold font-semibold text-xl mb-2">Days Free</div>
              <p className="text-gray-400">Full premium access. All features unlocked. Zero cost.</p>
            </div>
            <div className="bg-black/50 border border-gray-800 rounded-xl p-8 text-center">
              <div className="text-5xl mb-4">3,500</div>
              <div className="text-gold font-semibold text-xl mb-2">Minutes Included</div>
              <p className="text-gray-400">Queen Bee tier. Voice AI calls with sub-second response.</p>
            </div>
            <div className="bg-black/50 border border-gray-800 rounded-xl p-8 text-center">
              <div className="text-5xl mb-4">10</div>
              <div className="text-gold font-semibold text-xl mb-2">Voice Clones</div>
              <p className="text-gray-400">Create custom AI voices. Clone your own voice free.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Earn Points */}
      <div className="py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-4">Earn Points. Extend Your Trial.</h2>
          <p className="text-gray-400 text-center mb-12 max-w-2xl mx-auto">
            Invite friends, use features, and climb the leaderboard.
            Redeem points for more trial days and exclusive features.
          </p>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Earn */}
            <div className="bg-gray-900/30 border border-gray-800 rounded-xl p-8">
              <h3 className="text-xl font-semibold text-gold mb-6">How to Earn</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">Invite a friend (signup)</span>
                  <span className="text-gold font-bold">+100 pts</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">Complete first call</span>
                  <span className="text-gold font-bold">+50 pts</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">Use a feature</span>
                  <span className="text-gold font-bold">+25 pts</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">Send invite</span>
                  <span className="text-gold font-bold">+10 pts</span>
                </div>
                <div className="flex justify-between items-center py-3">
                  <span className="text-gray-300">Daily login</span>
                  <span className="text-gold font-bold">+5 pts</span>
                </div>
              </div>
            </div>

            {/* Redeem */}
            <div className="bg-gray-900/30 border border-gray-800 rounded-xl p-8">
              <h3 className="text-xl font-semibold text-gold mb-6">Redeem Rewards</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">+7 days trial extension</span>
                  <span className="text-white font-bold">200 pts</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">+30 days trial extension</span>
                  <span className="text-white font-bold">500 pts</span>
                </div>
                <div className="flex justify-between items-center py-3 border-b border-gray-800">
                  <span className="text-gray-300">Unlock voice cloning</span>
                  <span className="text-white font-bold">300 pts</span>
                </div>
                <div className="flex justify-between items-center py-3">
                  <span className="text-gray-300">+100 bonus minutes</span>
                  <span className="text-white font-bold">400 pts</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="py-20 bg-gradient-to-t from-gold/10 to-transparent">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-bold mb-6">Ready to Rise?</h2>
          <p className="text-xl text-gray-300 mb-8">
            Join the Early Risers and get 90 days of premium Voice AI for free.
          </p>
          <button
            onClick={handleJoin}
            className="px-12 py-4 bg-gold text-black font-bold text-lg rounded-lg hover:bg-gold/90 transition-colors"
          >
            START FREE TRIAL
          </button>
          <p className="text-gray-500 text-sm mt-4">
            Available until funding depletes. First come, first served.
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-gray-800 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-gray-500">
          <p>HIVE215 Voice AI Platform</p>
          <div className="mt-4 space-x-4">
            <Link href="/login" className="hover:text-gold">Login</Link>
            <Link href="/signup" className="hover:text-gold">Sign Up</Link>
            <Link href="/" className="hover:text-gold">Home</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
