'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { HoneycombButton } from './HoneycombButton';

interface TranscriptMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

interface VoiceCallProps {
  assistantId: string;
  assistantName: string;
  userId: string;
  onClose: () => void;
}

export function VoiceCall({ assistantId, assistantName, userId, onClose }: VoiceCallProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Play audio from queue
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    const audioB64 = audioQueueRef.current.shift();

    if (!audioB64) {
      isPlayingRef.current = false;
      return;
    }

    try {
      // Decode base64 to audio
      const audioData = atob(audioB64);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }

      // Create audio context if needed
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      const audioBuffer = await audioContextRef.current.decodeAudioData(audioArray.buffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        playNextAudio();
      };

      source.start();
    } catch (err) {
      console.error('Error playing audio:', err);
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    try {
      setError(null);

      // Get WebSocket URL from API URL
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');

      const ws = new WebSocket(`${wsUrl}/ws/voice/${assistantId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        // Send authentication
        ws.send(JSON.stringify({ type: 'auth', user_id: userId }));
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'ready':
            setIsConnected(true);
            setCallId(data.call_id);
            break;

          case 'transcript':
            setTranscript((prev) => [
              ...prev,
              { role: data.role, content: data.content },
            ]);
            break;

          case 'audio':
            audioQueueRef.current.push(data.data);
            playNextAudio();
            break;

          case 'speaking':
            setIsSpeaking(data.is_speaking);
            break;

          case 'error':
            setError(data.message);
            break;

          case 'call_ended':
            setIsConnected(false);
            break;
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('Connection error');
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        setIsConnected(false);
        setIsRecording(false);
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  }, [assistantId, userId, playNextAudio]);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          // Convert to base64 and send
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = (reader.result as string).split(',')[1];
            wsRef.current?.send(
              JSON.stringify({ type: 'audio', data: base64 })
            );
          };
          reader.readAsDataURL(event.data);
        }
      };

      // Record in chunks (every 3 seconds for complete utterances)
      mediaRecorder.start(3000);
      setIsRecording(true);
    } catch (err) {
      setError('Microphone access denied');
    }
  }, []);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
    }
    setIsRecording(false);
  }, []);

  // Send barge-in signal
  const handleBargeIn = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN && isSpeaking) {
      wsRef.current.send(JSON.stringify({ type: 'barge_in' }));
      // Clear audio queue
      audioQueueRef.current = [];
      isPlayingRef.current = false;
    }
  }, [isSpeaking]);

  // End call
  const endCall = useCallback(() => {
    stopRecording();

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
    }

    setIsConnected(false);
    onClose();
  }, [stopRecording, onClose]);

  // Connect on mount
  useEffect(() => {
    connect();

    return () => {
      stopRecording();
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [connect, stopRecording]);

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-oled-dark border border-gold/30 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gold/20 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-bold text-gold">{assistantName}</h2>
            <p className="text-sm text-gray-400">
              {isConnected ? (
                <span className="text-green-400">Connected</span>
              ) : (
                <span className="text-yellow-400">Connecting...</span>
              )}
              {callId && <span className="ml-2 text-gray-500">#{callId.slice(0, 8)}</span>}
            </p>
          </div>
          <button
            onClick={endCall}
            className="p-2 hover:bg-red-500/20 rounded-lg transition-colors"
          >
            <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Transcript */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {transcript.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              {isConnected ? 'Start speaking...' : 'Connecting to assistant...'}
            </div>
          ) : (
            transcript.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] p-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-gold/20 text-white'
                      : 'bg-gray-800 text-gray-100'
                  }`}
                >
                  <p className="text-xs text-gray-500 mb-1">
                    {msg.role === 'user' ? 'You' : assistantName}
                  </p>
                  <p>{msg.content}</p>
                </div>
              </div>
            ))
          )}
          <div ref={transcriptEndRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="mx-4 mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="p-4 border-t border-gold/20 flex justify-center gap-4">
          {/* Barge-in button */}
          {isSpeaking && (
            <button
              onClick={handleBargeIn}
              className="px-4 py-2 bg-orange-500/20 border border-orange-500/30 rounded-lg
                text-orange-400 hover:bg-orange-500/30 transition-colors"
            >
              Interrupt
            </button>
          )}

          {/* Record button */}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={!isConnected}
            className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
              isRecording
                ? 'bg-red-500 animate-pulse'
                : isConnected
                ? 'bg-gold hover:bg-gold/80'
                : 'bg-gray-600 cursor-not-allowed'
            }`}
          >
            {isRecording ? (
              <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
            ) : (
              <svg className="w-8 h-8 text-black" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
              </svg>
            )}
          </button>

          {/* End call button */}
          <button
            onClick={endCall}
            className="px-4 py-2 bg-red-500/20 border border-red-500/30 rounded-lg
              text-red-400 hover:bg-red-500/30 transition-colors"
          >
            End Call
          </button>
        </div>

        {/* Status indicator */}
        <div className="px-4 pb-4 text-center text-xs text-gray-500">
          {isSpeaking && <span className="text-gold animate-pulse">Assistant is speaking...</span>}
          {isRecording && !isSpeaking && <span className="text-green-400">Listening...</span>}
          {!isRecording && !isSpeaking && isConnected && <span>Press the microphone to speak</span>}
        </div>
      </div>
    </div>
  );
}
