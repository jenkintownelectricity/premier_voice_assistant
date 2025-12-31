'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';

interface ActiveCall {
  id: string;
  assistant_id: string;
  assistant_name: string;
  user_id: string;
  started_at: string;
  duration_seconds: number;
  status: 'active' | 'connecting' | 'on_hold';
  sentiment: 'positive' | 'neutral' | 'negative' | null;
  urgency: 'normal' | 'elevated' | 'urgent';
  transcript: Array<{ role: string; content: string; timestamp?: string }>;
  caller_info?: {
    name?: string;
    phone?: string;
  };
}

interface MonitoringConnection {
  callId: string;
  ws: WebSocket | null;
  isListening: boolean;
  audioContext: AudioContext | null;
}

export default function MonitoringPage() {
  const { user } = useAuth();
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<ActiveCall | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isTakingOver, setIsTakingOver] = useState(false);
  const [monitorVolume, setMonitorVolume] = useState(80);
  const [showTakeoverConfirm, setShowTakeoverConfirm] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch active calls
  const fetchActiveCalls = useCallback(async () => {
    if (!user?.id) return;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/calls/active`, {
        headers: {
          'X-User-ID': user.id,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setActiveCalls(data.calls || []);
      }
    } catch (err) {
      console.error('Failed to fetch active calls:', err);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  // Poll for active calls
  useEffect(() => {
    fetchActiveCalls();
    pollIntervalRef.current = setInterval(fetchActiveCalls, 3000); // Poll every 3 seconds

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [fetchActiveCalls]);

  // Play audio from queue
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
    isPlayingRef.current = true;

    const audioBase64 = audioQueueRef.current.shift()!;
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      const audioData = atob(audioBase64);
      const arrayBuffer = new ArrayBuffer(audioData.length);
      const view = new Uint8Array(arrayBuffer);
      for (let i = 0; i < audioData.length; i++) {
        view[i] = audioData.charCodeAt(i);
      }

      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
      const source = audioContextRef.current.createBufferSource();
      const gainNode = audioContextRef.current.createGain();

      gainNode.gain.value = monitorVolume / 100;
      source.buffer = audioBuffer;
      source.connect(gainNode);
      gainNode.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        playNextAudio();
      };
      source.start();
    } catch (err) {
      console.error('Audio playback error:', err);
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, [monitorVolume]);

  // Connect to monitor a call
  const startMonitoring = useCallback((call: ActiveCall) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setSelectedCall(call);
    setIsListening(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
    const wsUrl = apiUrl.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsUrl}/ws/monitor/${call.id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'auth',
        user_id: user?.id,
        mode: 'listen' // Listen-only mode
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'audio':
          // Queue audio for playback
          audioQueueRef.current.push(data.data);
          playNextAudio();
          break;

        case 'transcript':
          // Update transcript in real-time
          setSelectedCall(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              transcript: [...prev.transcript, { role: data.role, content: data.content }]
            };
          });
          break;

        case 'call_update':
          // Update call status/sentiment
          setSelectedCall(prev => {
            if (!prev) return prev;
            return { ...prev, ...data.update };
          });
          break;

        case 'call_ended':
          setIsListening(false);
          setSelectedCall(null);
          fetchActiveCalls();
          break;
      }
    };

    ws.onerror = () => {
      console.error('Monitor WebSocket error');
      setIsListening(false);
    };

    ws.onclose = () => {
      setIsListening(false);
    };
  }, [user?.id, playNextAudio, fetchActiveCalls]);

  // Stop monitoring
  const stopMonitoring = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsListening(false);
    audioQueueRef.current = [];
  }, []);

  // Take over the call
  const takeOverCall = useCallback(async () => {
    if (!selectedCall || !wsRef.current) return;

    setIsTakingOver(true);
    setShowTakeoverConfirm(false);

    // Send takeover command
    wsRef.current.send(JSON.stringify({
      type: 'takeover',
      user_id: user?.id,
    }));

    // The backend will switch the call to human mode
    // and we'll start receiving/sending audio as the operator
  }, [selectedCall, user?.id]);

  // Release call back to AI
  const releaseCall = useCallback(() => {
    if (!wsRef.current) return;

    wsRef.current.send(JSON.stringify({
      type: 'release',
      user_id: user?.id,
    }));

    setIsTakingOver(false);
  }, [user?.id]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getSentimentColor = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive': return 'text-green-400 bg-green-500/20';
      case 'negative': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'urgent': return 'text-red-400 bg-red-500/20 border-red-500 animate-pulse';
      case 'elevated': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500';
      default: return 'text-green-400 bg-green-500/20 border-green-500';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading monitoring dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gold">Live Call Monitoring</h1>
          <p className="text-gray-400 mt-1">
            Monitor active calls in real-time and take over when needed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${activeCalls.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-gray-400">{activeCalls.length} active call{activeCalls.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Active Calls Grid */}
      {activeCalls.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-16">
              <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-4">
                <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </div>
              <h3 className="text-xl text-white mb-2">No Active Calls</h3>
              <p className="text-gray-400">
                When customers call your assistants, they will appear here for monitoring.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeCalls.map((call) => (
            <Card key={call.id} glow={call.urgency === 'urgent'}>
              <CardContent>
                <div className="space-y-4">
                  {/* Call Header */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center">
                        <span className="text-lg font-bold text-black">
                          {call.assistant_name.charAt(0)}
                        </span>
                      </div>
                      <div>
                        <h3 className="text-white font-semibold">{call.assistant_name}</h3>
                        <p className="text-sm text-gray-400">{formatTime(call.started_at)}</p>
                      </div>
                    </div>
                    <div className={`px-2 py-1 rounded-full text-xs border ${getUrgencyColor(call.urgency)}`}>
                      {call.urgency === 'urgent' ? '🚨 URGENT' : call.urgency === 'elevated' ? '⚡ Elevated' : 'Normal'}
                    </div>
                  </div>

                  {/* Call Stats */}
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1">
                      <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="text-white font-mono">{formatDuration(call.duration_seconds)}</span>
                    </div>
                    {call.sentiment && (
                      <span className={`px-2 py-0.5 rounded text-xs ${getSentimentColor(call.sentiment)}`}>
                        {call.sentiment}
                      </span>
                    )}
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      <span className="text-green-400 text-xs">Live</span>
                    </div>
                  </div>

                  {/* Caller Info */}
                  {call.caller_info && (
                    <div className="bg-zinc-800/50 rounded-lg p-3 text-sm">
                      {call.caller_info.name && (
                        <div className="text-white">{call.caller_info.name}</div>
                      )}
                      {call.caller_info.phone && (
                        <div className="text-gray-400">{call.caller_info.phone}</div>
                      )}
                    </div>
                  )}

                  {/* Last Message Preview */}
                  {call.transcript.length > 0 && (
                    <div className="bg-zinc-800/50 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">
                        {call.transcript[call.transcript.length - 1].role === 'user' ? 'Caller' : 'Assistant'}
                      </div>
                      <p className="text-sm text-gray-300 line-clamp-2">
                        {call.transcript[call.transcript.length - 1].content}
                      </p>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => startMonitoring(call)}
                      className="flex-1 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                      </svg>
                      Listen
                    </button>
                    <button
                      onClick={() => {
                        setSelectedCall(call);
                        setShowTakeoverConfirm(true);
                      }}
                      className="flex-1 py-2 bg-amber-500 hover:bg-amber-600 text-black rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Take Over
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Monitoring Panel (when listening to a call) */}
      {selectedCall && isListening && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="max-w-4xl w-full bg-zinc-900 rounded-xl border border-gold/20 overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-center p-4 border-b border-gold/10 bg-zinc-800">
              <div className="flex items-center gap-4">
                <div className="relative">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center">
                    <span className="text-xl font-bold text-black">
                      {selectedCall.assistant_name.charAt(0)}
                    </span>
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-green-500 border-2 border-zinc-800" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">{selectedCall.assistant_name}</h2>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-green-400">● Live</span>
                    <span className="text-gray-400">{formatDuration(selectedCall.duration_seconds)}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {isTakingOver && (
                  <span className="px-3 py-1 bg-amber-500 text-black text-sm font-medium rounded-full">
                    You're on the call
                  </span>
                )}
                <button
                  onClick={stopMonitoring}
                  className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-zinc-700"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Main Content */}
            <div className="grid md:grid-cols-2 gap-0">
              {/* Transcript */}
              <div className="border-r border-gold/10 p-4 h-96 overflow-y-auto">
                <h3 className="text-sm font-medium text-gray-400 mb-3">Live Transcript</h3>
                <div className="space-y-3">
                  {selectedCall.transcript.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm ${
                        msg.role === 'user'
                          ? 'bg-amber-500/20 text-amber-200'
                          : 'bg-zinc-800 text-white'
                      }`}>
                        <div className="text-xs text-gray-500 mb-1">
                          {msg.role === 'user' ? 'Caller' : 'Assistant'}
                        </div>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Controls */}
              <div className="p-4 flex flex-col">
                <h3 className="text-sm font-medium text-gray-400 mb-3">Monitor Controls</h3>

                {/* Volume Control */}
                <div className="bg-zinc-800 rounded-lg p-4 mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white">Monitor Volume</span>
                    <span className="text-sm text-gold">{monitorVolume}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={monitorVolume}
                    onChange={(e) => setMonitorVolume(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>

                {/* Call Info */}
                <div className="bg-zinc-800 rounded-lg p-4 mb-4 flex-1">
                  <h4 className="text-sm font-medium text-gray-400 mb-3">Call Information</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Status</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${getSentimentColor(selectedCall.sentiment)}`}>
                        {selectedCall.sentiment || 'neutral'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Urgency</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${getUrgencyColor(selectedCall.urgency)}`}>
                        {selectedCall.urgency}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Duration</span>
                      <span className="text-white font-mono">{formatDuration(selectedCall.duration_seconds)}</span>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="space-y-2">
                  {!isTakingOver ? (
                    <button
                      onClick={() => setShowTakeoverConfirm(true)}
                      className="w-full py-3 bg-amber-500 hover:bg-amber-600 text-black font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Take Over Call
                    </button>
                  ) : (
                    <button
                      onClick={releaseCall}
                      className="w-full py-3 bg-zinc-700 hover:bg-zinc-600 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      Release to AI
                    </button>
                  )}
                  <button
                    onClick={stopMonitoring}
                    className="w-full py-3 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-semibold rounded-lg transition-colors"
                  >
                    Stop Monitoring
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Takeover Confirmation Modal */}
      {showTakeoverConfirm && (
        <div className="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-zinc-900 rounded-xl border border-gold/20 p-6">
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Take Over Call?</h3>
              <p className="text-gray-400">
                You will replace the AI assistant and speak directly with the caller.
                Make sure your microphone is ready.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowTakeoverConfirm(false)}
                className="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={takeOverCall}
                className="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-black rounded-lg font-medium transition-colors"
              >
                Take Over
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
