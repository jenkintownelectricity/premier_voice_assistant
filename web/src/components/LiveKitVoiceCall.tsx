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

  // Handle data messages (transcripts) from agent
  const { message: dataMessage } = useDataChannel('transcript');

  useEffect(() => {
    if (dataMessage) {
      try {
        const data = JSON.parse(new TextDecoder().decode(dataMessage.payload));
        if (data.type === 'transcript' && data.content) {
          setTranscript(prev => [...prev, {
            role: data.role || 'assistant',
            content: data.content,
            timestamp: Date.now(),
          }]);
        }
      } catch (e) {
        console.error('Failed to parse data message:', e);
      }
    }
  }, [dataMessage]);

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
          <button onClick={endCall} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

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

      {/* Latency Info Banner */}
      <div className="mx-4 mt-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg px-3 py-2">
        <div className="flex items-center gap-2 text-cyan-400 text-xs">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>~50-100ms faster than WebSocket</span>
        </div>
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
