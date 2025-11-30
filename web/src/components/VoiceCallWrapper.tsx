'use client';

import { useState, useEffect } from 'react';
import { VoiceCall } from './VoiceCall';
import { LiveKitVoiceCall } from './LiveKitVoiceCall';

interface VoiceCallWrapperProps {
  assistantId: string;
  assistantName: string;
  userId: string;
  onClose: () => void;
  defaultMode?: 'websocket' | 'livekit';
}

interface LiveKitStatus {
  enabled: boolean;
  configured: boolean;
  url?: string;
  message: string;
}

/**
 * VoiceCallWrapper - Smart wrapper that chooses between WebSocket and LiveKit
 *
 * Features:
 * - Auto-detects if LiveKit is available
 * - Allows manual mode switching
 * - Falls back to WebSocket if LiveKit fails
 *
 * Latency comparison:
 * - WebSocket (TCP): ~300-500ms voice-to-voice
 * - LiveKit (WebRTC/UDP): ~200-300ms voice-to-voice
 */
export function VoiceCallWrapper({
  assistantId,
  assistantName,
  userId,
  onClose,
  defaultMode = 'websocket',
}: VoiceCallWrapperProps) {
  const [mode, setMode] = useState<'websocket' | 'livekit'>(defaultMode);
  const [liveKitStatus, setLiveKitStatus] = useState<LiveKitStatus | null>(null);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [isCheckingLiveKit, setIsCheckingLiveKit] = useState(true);

  // Check LiveKit availability on mount
  useEffect(() => {
    const checkLiveKit = async () => {
      setIsCheckingLiveKit(true);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
        const response = await fetch(`${apiUrl}/livekit/status`);

        if (response.ok) {
          const status = await response.json();
          setLiveKitStatus(status);

          // Auto-switch to LiveKit if available and configured
          if (status.enabled && status.configured && defaultMode === 'livekit') {
            setMode('livekit');
          }
        } else {
          setLiveKitStatus({
            enabled: false,
            configured: false,
            message: 'LiveKit endpoint not available',
          });
        }
      } catch (err) {
        console.error('Failed to check LiveKit status:', err);
        setLiveKitStatus({
          enabled: false,
          configured: false,
          message: 'Failed to check LiveKit status',
        });
      } finally {
        setIsCheckingLiveKit(false);
      }
    };

    checkLiveKit();
  }, [defaultMode]);

  // Mode selector overlay
  if (showModeSelector) {
    return (
      <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
        <div className="p-4 flex items-center justify-between border-b border-zinc-800">
          <h2 className="text-white font-semibold">Select Connection Mode</h2>
          <button
            onClick={() => setShowModeSelector(false)}
            className="text-zinc-400 hover:text-white p-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 p-4 space-y-4">
          {/* WebSocket Mode */}
          <button
            onClick={() => {
              setMode('websocket');
              setShowModeSelector(false);
            }}
            className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
              mode === 'websocket'
                ? 'border-amber-500 bg-amber-500/10'
                : 'border-zinc-700 hover:border-zinc-600 bg-zinc-800/50'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <span className="text-xl">🔌</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-white font-semibold">WebSocket</h3>
                  <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                    Stable
                  </span>
                </div>
                <p className="text-zinc-400 text-sm mt-1">
                  Traditional TCP-based connection
                </p>
                <div className="mt-2 space-y-1">
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <span className="text-yellow-400">~300-500ms</span>
                    <span>voice-to-voice latency</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <span>TCP Protocol</span>
                    <span className="text-zinc-600">|</span>
                    <span>Reliable delivery</span>
                  </div>
                </div>
              </div>
              {mode === 'websocket' && (
                <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </div>
          </button>

          {/* LiveKit Mode */}
          <button
            onClick={() => {
              if (liveKitStatus?.enabled && liveKitStatus?.configured) {
                setMode('livekit');
                setShowModeSelector(false);
              }
            }}
            disabled={!liveKitStatus?.enabled || !liveKitStatus?.configured}
            className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
              mode === 'livekit'
                ? 'border-cyan-500 bg-cyan-500/10'
                : liveKitStatus?.enabled && liveKitStatus?.configured
                ? 'border-zinc-700 hover:border-zinc-600 bg-zinc-800/50'
                : 'border-zinc-800 bg-zinc-900/50 opacity-60 cursor-not-allowed'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <span className="text-xl">⚡</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-white font-semibold">LiveKit WebRTC</h3>
                  {liveKitStatus?.enabled && liveKitStatus?.configured ? (
                    <span className="px-2 py-0.5 text-xs bg-cyan-500/20 text-cyan-400 rounded">
                      Available
                    </span>
                  ) : isCheckingLiveKit ? (
                    <span className="px-2 py-0.5 text-xs bg-zinc-700 text-zinc-400 rounded">
                      Checking...
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded">
                      Not Configured
                    </span>
                  )}
                </div>
                <p className="text-zinc-400 text-sm mt-1">
                  Ultra-low latency UDP transport
                </p>
                <div className="mt-2 space-y-1">
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <span className="text-cyan-400">~200-300ms</span>
                    <span>voice-to-voice latency</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <span>WebRTC/UDP</span>
                    <span className="text-zinc-600">|</span>
                    <span>50-100ms faster</span>
                  </div>
                </div>
                {!liveKitStatus?.enabled && !isCheckingLiveKit && (
                  <p className="text-red-400/70 text-xs mt-2">
                    {liveKitStatus?.message || 'LiveKit not configured'}
                  </p>
                )}
              </div>
              {mode === 'livekit' && (
                <div className="w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </div>
          </button>
        </div>

        {/* Info Section */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-800/30">
          <div className="text-xs text-zinc-500 space-y-1">
            <p>
              <span className="text-zinc-400">WebRTC</span> uses UDP for faster audio delivery,
              while <span className="text-zinc-400">WebSocket</span> uses TCP for reliability.
            </p>
            <p>
              Choose WebRTC for the lowest latency. WebSocket is more widely compatible.
            </p>
          </div>
        </div>

        {/* Start Call Button */}
        <div className="p-4 border-t border-zinc-800">
          <button
            onClick={() => setShowModeSelector(false)}
            className={`w-full py-3 font-semibold rounded-xl transition-colors ${
              mode === 'livekit'
                ? 'bg-cyan-500 hover:bg-cyan-600 text-black'
                : 'bg-amber-500 hover:bg-amber-600 text-black'
            }`}
          >
            Start Call ({mode === 'livekit' ? 'WebRTC' : 'WebSocket'})
          </button>
        </div>
      </div>
    );
  }

  // Render the appropriate call component
  if (mode === 'livekit' && liveKitStatus?.enabled && liveKitStatus?.configured) {
    return (
      <LiveKitVoiceCall
        assistantId={assistantId}
        assistantName={assistantName}
        userId={userId}
        onClose={onClose}
      />
    );
  }

  // Default to WebSocket
  return (
    <VoiceCall
      assistantId={assistantId}
      assistantName={assistantName}
      userId={userId}
      onClose={onClose}
    />
  );
}

/**
 * Hook to get LiveKit availability status
 */
export function useLiveKitStatus() {
  const [status, setStatus] = useState<LiveKitStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
        const response = await fetch(`${apiUrl}/livekit/status`);
        if (response.ok) {
          setStatus(await response.json());
        }
      } catch (err) {
        console.error('Failed to check LiveKit status:', err);
      } finally {
        setLoading(false);
      }
    };

    checkStatus();
  }, []);

  return { status, loading, isAvailable: status?.enabled && status?.configured };
}

export default VoiceCallWrapper;
