'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  LiveKitRoom,
  useRoomContext,
  useTracks,
  useParticipants,
  useLocalParticipant,
  RoomAudioRenderer,
  useConnectionState,
  useDataChannel,
} from '@livekit/components-react';
import '@livekit/components-styles';
import { Track, RoomEvent, ConnectionState, DataPacket_Kind } from 'livekit-client';

interface TranscriptMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

interface LatencyMetrics {
  stt_ms: number;
  llm_ttft_ms: number;
  llm_total_ms: number;
  tts_ttfb_ms: number;
  tts_total_ms: number;
  total_ms: number;
}

interface PipelineConfig {
  llm: string;
  stt: string;
  tts: string;
  voice_id: string;
}

interface CallSettings {
  temperature: number;
  speechSpeed: number;
  bargeInEnabled: boolean;
  bargeInSensitivity: 'low' | 'medium' | 'high';
}

interface LiveKitVoiceCallProps {
  assistantId: string;
  assistantName: string;
  userId: string;
  onClose: () => void;
}

interface RoomConnectionData {
  room_name: string;
  token: string;
  url: string;
  call_id: string | null;
}

/**
 * LiveKitVoiceCall - WebRTC-powered voice call component
 *
 * Uses LiveKit for ultra-low latency voice communication:
 * - WebRTC (UDP) transport: ~10-20ms latency
 * - Built-in echo cancellation and noise suppression
 * - Automatic reconnection and quality adaptation
 *
 * Total voice-to-voice latency: ~200-300ms (vs ~400-500ms with WebSocket)
 */
export function LiveKitVoiceCall({
  assistantId,
  assistantName,
  userId,
  onClose,
}: LiveKitVoiceCallProps) {
  const [connectionData, setConnectionData] = useState<RoomConnectionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(true);

  // Fetch LiveKit room token on mount
  useEffect(() => {
    const createRoom = async () => {
      setIsConnecting(true);
      setError(null);

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
        const response = await fetch(`${apiUrl}/livekit/rooms`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': userId,
          },
          body: JSON.stringify({
            assistant_id: assistantId,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to create room');
        }

        const data = await response.json();
        setConnectionData(data);
      } catch (err) {
        console.error('Failed to create LiveKit room:', err);
        setError(err instanceof Error ? err.message : 'Failed to connect');
      } finally {
        setIsConnecting(false);
      }
    };

    createRoom();
  }, [assistantId, userId]);

  // Cleanup room on unmount
  useEffect(() => {
    return () => {
      if (connectionData?.room_name) {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
        // Fire and forget cleanup
        fetch(`${apiUrl}/livekit/rooms/${connectionData.room_name}`, {
          method: 'DELETE',
          headers: { 'X-User-ID': userId },
        }).catch(console.error);
      }
    };
  }, [connectionData?.room_name, userId]);

  if (isConnecting) {
    return (
      <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-zinc-400">Connecting via WebRTC...</p>
            <p className="text-zinc-500 text-sm mt-2">Ultra-low latency mode</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !connectionData) {
    return (
      <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
        <div className="p-4 flex items-center justify-between border-b border-zinc-800">
          <span className="text-red-400">Connection Error</span>
          <button onClick={onClose} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-white font-medium mb-2">Failed to Connect</p>
            <p className="text-zinc-400 text-sm mb-4">{error || 'Unknown error'}</p>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={connectionData.url}
      token={connectionData.token}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={() => {
        console.log('Disconnected from LiveKit room');
      }}
      onError={(err) => {
        console.error('LiveKit error:', err);
        setError(err.message);
      }}
    >
      <ActiveCall
        assistantName={assistantName}
        callId={connectionData.call_id}
        onClose={onClose}
      />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

/**
 * ActiveCall - The main call UI when connected to LiveKit
 */
function ActiveCall({
  assistantName,
  callId,
  onClose,
}: {
  assistantName: string;
  callId: string | null;
  onClose: () => void;
}) {
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const { localParticipant } = useLocalParticipant();
  const participants = useParticipants();

  const [isMuted, setIsMuted] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [callDuration, setCallDuration] = useState(0);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [latencyMetrics, setLatencyMetrics] = useState<LatencyMetrics | null>(null);
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig | null>(null);
  const [showLatencyPanel, setShowLatencyPanel] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<CallSettings>({
    temperature: 0.7,
    speechSpeed: 1.0,
    bargeInEnabled: true,
    bargeInSensitivity: 'medium',
  });
  const [isRecording, setIsRecording] = useState(false);
  const [recordingId, setRecordingId] = useState<string | null>(null);

  const callTimerRef = useRef<NodeJS.Timeout | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Find the agent participant
  const agentParticipant = participants.find(p =>
    p.identity.startsWith('agent-') || p.identity.includes('agent')
  );

  // Track audio levels from agent
  const agentTracks = useTracks([Track.Source.Microphone], {
    onlySubscribed: true,
  }).filter(track => track.participant !== localParticipant);

  // Handle data messages from agent
  const { message: transcriptMessage } = useDataChannel('transcript');
  const { message: latencyMessage } = useDataChannel('latency');
  const { message: configMessage } = useDataChannel('config');

  // Process transcript messages
  useEffect(() => {
    if (transcriptMessage) {
      try {
        const data = JSON.parse(new TextDecoder().decode(transcriptMessage.payload));
        if (data.type === 'transcript' && data.content) {
          setTranscript(prev => [...prev, {
            role: data.role || 'assistant',
            content: data.content,
            timestamp: Date.now(),
          }]);
        }
      } catch (e) {
        console.error('Failed to parse transcript message:', e);
      }
    }
  }, [transcriptMessage]);

  // Process latency metrics
  useEffect(() => {
    if (latencyMessage) {
      try {
        const data = JSON.parse(new TextDecoder().decode(latencyMessage.payload));
        if (data.type === 'latency') {
          setLatencyMetrics({
            stt_ms: data.stt_ms || 0,
            llm_ttft_ms: data.llm_ttft_ms || 0,
            llm_total_ms: data.llm_total_ms || 0,
            tts_ttfb_ms: data.tts_ttfb_ms || 0,
            tts_total_ms: data.tts_total_ms || 0,
            total_ms: data.total_ms || 0,
          });
        }
      } catch (e) {
        console.error('Failed to parse latency message:', e);
      }
    }
  }, [latencyMessage]);

  // Process pipeline config
  useEffect(() => {
    if (configMessage) {
      try {
        const data = JSON.parse(new TextDecoder().decode(configMessage.payload));
        if (data.type === 'config') {
          setPipelineConfig({
            llm: data.llm || 'unknown',
            stt: data.stt || 'unknown',
            tts: data.tts || 'unknown',
            voice_id: data.voice_id || '',
          });
        }
      } catch (e) {
        console.error('Failed to parse config message:', e);
      }
    }
  }, [configMessage]);

  // Listen for room events
  useEffect(() => {
    if (!room) return;

    const handleTrackSubscribed = () => {
      console.log('Track subscribed - agent audio available');
    };

    const handleActiveSpeakersChanged = (speakers: any[]) => {
      const agentSpeaking = speakers.some(s =>
        s.identity?.startsWith('agent-') || s.identity?.includes('agent')
      );
      setIsAgentSpeaking(agentSpeaking);
    };

    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakersChanged);

    return () => {
      room.off(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.off(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakersChanged);
    };
  }, [room]);

  // Start call timer when connected
  useEffect(() => {
    if (connectionState === ConnectionState.Connected) {
      callTimerRef.current = setInterval(() => {
        setCallDuration(d => d + 1);
      }, 1000);
    }

    return () => {
      if (callTimerRef.current) {
        clearInterval(callTimerRef.current);
      }
    };
  }, [connectionState]);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Monitor local audio level
  useEffect(() => {
    if (!localParticipant) return;

    const interval = setInterval(() => {
      const audioTrack = localParticipant.getTrackPublication(Track.Source.Microphone);
      if (audioTrack?.track) {
        // Audio level is 0-1
        const level = localParticipant.audioLevel || 0;
        setAudioLevel(Math.round(level * 100));
      }
    }, 100);

    return () => clearInterval(interval);
  }, [localParticipant]);

  const toggleMute = useCallback(async () => {
    if (!localParticipant) return;

    await localParticipant.setMicrophoneEnabled(isMuted);
    setIsMuted(!isMuted);
  }, [localParticipant, isMuted]);

  const endCall = useCallback(() => {
    room?.disconnect();
    onClose();
  }, [room, onClose]);

  // Send settings update to agent
  const updateSettings = useCallback(async (newSettings: Partial<CallSettings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);

    if (room && localParticipant) {
      try {
        const data = JSON.stringify({
          type: 'settings',
          ...updated,
        });
        await localParticipant.publishData(
          new TextEncoder().encode(data),
          { topic: 'settings', reliable: true }
        );
        console.log('Settings sent to agent:', updated);
      } catch (e) {
        console.error('Failed to send settings:', e);
      }
    }
  }, [room, localParticipant, settings]);

  // Toggle recording
  const toggleRecording = useCallback(async () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
    const roomName = room?.name;

    if (!roomName) return;

    try {
      if (isRecording && recordingId) {
        // Stop recording
        const response = await fetch(`${apiUrl}/livekit/recordings/${recordingId}/stop`, {
          method: 'POST',
          headers: { 'X-User-ID': 'user' },
        });
        if (response.ok) {
          setIsRecording(false);
          setRecordingId(null);
          console.log('Recording stopped');
        }
      } else {
        // Start recording
        const response = await fetch(`${apiUrl}/livekit/recordings/start`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': 'user',
          },
          body: JSON.stringify({ room_name: roomName }),
        });
        if (response.ok) {
          const data = await response.json();
          setIsRecording(true);
          setRecordingId(data.egress_id);
          console.log('Recording started:', data.egress_id);
        } else {
          const error = await response.json();
          console.error('Failed to start recording:', error.detail);
        }
      }
    } catch (e) {
      console.error('Recording toggle failed:', e);
    }
  }, [room, isRecording, recordingId]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getConnectionStatusInfo = () => {
    switch (connectionState) {
      case ConnectionState.Connected:
        return { color: 'bg-green-500', label: 'WebRTC', icon: '⚡' };
      case ConnectionState.Connecting:
        return { color: 'bg-yellow-500', label: 'Connecting', icon: '...' };
      case ConnectionState.Reconnecting:
        return { color: 'bg-yellow-500', label: 'Reconnecting', icon: '🔄' };
      default:
        return { color: 'bg-red-500', label: 'Disconnected', icon: '❌' };
    }
  };

  const status = getConnectionStatusInfo();

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
      {/* Header */}
      <div className="p-4 flex items-center justify-between border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center ${
            isAgentSpeaking ? 'ring-2 ring-cyan-400 ring-opacity-60 animate-pulse' : ''
          }`}>
            <span className="text-lg font-bold text-black">
              {assistantName.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">{assistantName}</h1>
            <p className="text-xs text-zinc-400 font-mono">
              {connectionState === ConnectionState.Connected
                ? formatDuration(callDuration)
                : 'Connecting...'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Connection Status */}
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${status.color} ${
              connectionState === ConnectionState.Connected ? 'animate-pulse' : ''
            }`} />
            <span className="text-xs font-medium text-cyan-400">
              {status.icon} {status.label}
            </span>
          </div>
          {/* Settings Button */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg transition-colors ${showSettings ? 'bg-cyan-500/20 text-cyan-400' : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          <button onClick={endCall} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Settings Panel (Overlay) */}
      {showSettings && (
        <div className="absolute top-16 right-4 w-72 bg-zinc-800 border border-zinc-700 rounded-xl shadow-2xl z-10">
          <div className="p-3 border-b border-zinc-700 flex items-center justify-between">
            <h3 className="text-white font-semibold text-sm">Call Settings</h3>
            <button onClick={() => setShowSettings(false)} className="text-zinc-400 hover:text-white">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="p-4 space-y-4">
            {/* Temperature Slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-zinc-400">Temperature</label>
                <span className="text-xs font-mono text-cyan-400">{settings.temperature.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
                className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
              <div className="flex justify-between text-xs text-zinc-500 mt-1">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>

            {/* Speech Speed Slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-zinc-400">Speech Speed</label>
                <span className="text-xs font-mono text-cyan-400">{settings.speechSpeed.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={settings.speechSpeed}
                onChange={(e) => updateSettings({ speechSpeed: parseFloat(e.target.value) })}
                className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
              <div className="flex justify-between text-xs text-zinc-500 mt-1">
                <span>0.5x</span>
                <span>1x</span>
                <span>2x</span>
              </div>
            </div>

            {/* Barge-In Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-xs text-zinc-400 block">Allow Interruptions</label>
                <span className="text-xs text-zinc-500">Speak over the assistant</span>
              </div>
              <button
                onClick={() => updateSettings({ bargeInEnabled: !settings.bargeInEnabled })}
                className={`w-11 h-6 rounded-full transition-colors relative ${
                  settings.bargeInEnabled ? 'bg-cyan-500' : 'bg-zinc-600'
                }`}
              >
                <div
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.bargeInEnabled ? 'left-6' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Barge-In Sensitivity */}
            {settings.bargeInEnabled && (
              <div>
                <label className="text-xs text-zinc-400 block mb-2">Interruption Sensitivity</label>
                <div className="flex gap-2">
                  {(['low', 'medium', 'high'] as const).map((level) => (
                    <button
                      key={level}
                      onClick={() => updateSettings({ bargeInSensitivity: level })}
                      className={`flex-1 py-1.5 text-xs rounded-lg capitalize transition-colors ${
                        settings.bargeInSensitivity === level
                          ? 'bg-cyan-500 text-black font-medium'
                          : 'bg-zinc-700 text-zinc-400 hover:bg-zinc-600'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="p-3 border-t border-zinc-700 text-xs text-zinc-500">
            Settings apply in real-time
          </div>
        </div>
      )}

      {/* Status Bar */}
      <div className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-zinc-400">
          <span className="text-cyan-400">⚡</span>
          <span>WebRTC Ultra-Low Latency</span>
        </div>
        <div className="flex items-center gap-3">
          {audioLevel > 10 && <span className="text-green-400">● Listening</span>}
          {isAgentSpeaking && <span className="text-cyan-400">● Speaking</span>}
          {agentParticipant && <span className="text-green-400">Agent Connected</span>}
        </div>
      </div>

      {/* Latency Metrics Panel */}
      <div className="mx-4 mt-3">
        <button
          onClick={() => setShowLatencyPanel(!showLatencyPanel)}
          className="w-full bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 flex items-center justify-between hover:bg-zinc-800 transition-colors"
        >
          <div className="flex items-center gap-2 text-cyan-400 text-xs">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span>
              {latencyMetrics ? `${latencyMetrics.total_ms}ms total latency` : 'Awaiting metrics...'}
            </span>
          </div>
          <svg
            className={`w-4 h-4 text-zinc-400 transition-transform ${showLatencyPanel ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showLatencyPanel && (
          <div className="mt-2 bg-zinc-800/30 border border-zinc-700/50 rounded-lg p-3 space-y-2">
            {/* Pipeline Config */}
            {pipelineConfig && (
              <div className="text-xs text-zinc-500 pb-2 border-b border-zinc-700/50">
                <span className="text-zinc-400">LLM:</span> {pipelineConfig.llm} •{' '}
                <span className="text-zinc-400">STT:</span> {pipelineConfig.stt} •{' '}
                <span className="text-zinc-400">TTS:</span> {pipelineConfig.tts}
              </div>
            )}

            {/* Latency Breakdown */}
            {latencyMetrics ? (
              <div className="space-y-1.5">
                {/* STT */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">STT (Deepgram)</span>
                  <span className={`font-mono ${latencyMetrics.stt_ms < 100 ? 'text-green-400' : latencyMetrics.stt_ms < 200 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {latencyMetrics.stt_ms}ms
                  </span>
                </div>
                <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${latencyMetrics.stt_ms < 100 ? 'bg-green-500' : latencyMetrics.stt_ms < 200 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(100, latencyMetrics.stt_ms / 3)}%` }}
                  />
                </div>

                {/* LLM */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">LLM (TTFT)</span>
                  <span className={`font-mono ${latencyMetrics.llm_ttft_ms < 100 ? 'text-green-400' : latencyMetrics.llm_ttft_ms < 200 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {latencyMetrics.llm_ttft_ms}ms
                  </span>
                </div>
                <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${latencyMetrics.llm_ttft_ms < 100 ? 'bg-green-500' : latencyMetrics.llm_ttft_ms < 200 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(100, latencyMetrics.llm_ttft_ms / 3)}%` }}
                  />
                </div>

                {/* TTS */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">TTS (TTFB)</span>
                  <span className={`font-mono ${latencyMetrics.tts_ttfb_ms < 100 ? 'text-green-400' : latencyMetrics.tts_ttfb_ms < 200 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {latencyMetrics.tts_ttfb_ms}ms
                  </span>
                </div>
                <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${latencyMetrics.tts_ttfb_ms < 100 ? 'bg-green-500' : latencyMetrics.tts_ttfb_ms < 200 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(100, latencyMetrics.tts_ttfb_ms / 3)}%` }}
                  />
                </div>

                {/* Total */}
                <div className="flex items-center justify-between text-xs pt-2 border-t border-zinc-700/50">
                  <span className="text-white font-medium">Total Perceived</span>
                  <span className={`font-mono font-bold ${latencyMetrics.total_ms < 250 ? 'text-green-400' : latencyMetrics.total_ms < 400 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {latencyMetrics.total_ms}ms
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-center text-zinc-500 text-xs py-2">
                Latency metrics will appear after first response
              </div>
            )}
          </div>
        )}
      </div>

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 && connectionState === ConnectionState.Connected && (
          <div className="text-center text-zinc-500 text-sm py-8">
            {agentParticipant
              ? 'Start speaking to begin the conversation...'
              : 'Waiting for AI agent to join...'}
          </div>
        )}
        {transcript.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm ${
              msg.role === 'user'
                ? 'bg-cyan-500 text-black rounded-br-sm'
                : 'bg-zinc-800 text-white rounded-bl-sm'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      {/* Audio Level Indicator */}
      <div className="px-4 py-2 border-t border-zinc-800">
        <div className="flex items-center gap-0.5 h-6 justify-center">
          {[...Array(30)].map((_, i) => (
            <div
              key={i}
              className={`w-1 rounded-full transition-all duration-75 ${
                isMuted ? 'bg-zinc-700' :
                i < audioLevel / 3.3 ? (audioLevel > 10 ? 'bg-cyan-400' : 'bg-zinc-600') : 'bg-zinc-800'
              }`}
              style={{
                height: `${Math.max(4, Math.sin((i / 30) * Math.PI) * 24)}px`
              }}
            />
          ))}
        </div>
      </div>

      {/* Bottom Controls */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center justify-center gap-4">
          {/* Mute Button */}
          <button
            onClick={toggleMute}
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
              isMuted
                ? 'bg-white text-black'
                : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            {isMuted ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            )}
          </button>

          {/* Recording Button */}
          <button
            onClick={toggleRecording}
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
              isRecording
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
            title={isRecording ? 'Stop Recording' : 'Start Recording'}
          >
            {isRecording ? (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="8" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" strokeWidth={2} />
                <circle cx="12" cy="12" r="4" fill="currentColor" />
              </svg>
            )}
          </button>

          {/* End Call Button */}
          <button
            onClick={endCall}
            className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors"
          >
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.28 3H5z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default LiveKitVoiceCall;
