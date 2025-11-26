'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Volume2 } from 'lucide-react';

interface VoiceCallProps {
  assistantId: string;
  assistantName: string;
  userId: string;
  onClose: () => void;
}

export default function VoiceCall({
  assistantId,
  assistantName,
  userId,
  onClose,
}: VoiceCallProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Array<{ role: string; content: string }>>([]);
  const [callDuration, setCallDuration] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  // NEW: Store audio chunks instead of sending immediately
  const audioChunksRef = useRef<Blob[]>([]);

  // Play audio from base64
  const playAudio = useCallback(async (audioBase64: string) => {
    try {
      const audioData = atob(audioBase64);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      const audioBuffer = await audioContextRef.current.decodeAudioData(audioArray.buffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.start();
    } catch (err) {
      console.error('Error playing audio:', err);
    }
  }, []);

  // Connect WebSocket
  const connect = useCallback(async () => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8080';
      const wsUrl = backendUrl.replace('http', 'ws');

      const ws = new WebSocket(`${wsUrl}/ws/voice/${assistantId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        ws.send(JSON.stringify({ type: 'auth', user_id: userId }));
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'ready':
            setIsConnected(true);
            setError(null);
            // Start duration timer
            timerRef.current = setInterval(() => {
              setCallDuration((prev) => prev + 1);
            }, 1000);
            break;

          case 'transcript':
            setTranscript((prev) => [
              ...prev,
              { role: data.role, content: data.content },
            ]);
            break;

          case 'audio':
            await playAudio(data.data);
            break;

          case 'speaking':
            setIsSpeaking(data.is_speaking);
            break;

          case 'error':
            setError(data.message);
            break;

          case 'call_ended':
            disconnect();
            break;
        }
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        setIsConnected(false);
        setIsRecording(false);
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Connection error');
      };
    } catch (err) {
      setError('Failed to connect');
    }
  }, [assistantId, userId, playAudio]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
      wsRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsConnected(false);
    setIsRecording(false);
    setCallDuration(0);
  }, []);

  // NEW: Send accumulated audio as one complete file
  const sendAccumulatedAudio = useCallback(() => {
    if (audioChunksRef.current.length === 0) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Combine all chunks into a single valid webm blob
    const completeBlob = new Blob(audioChunksRef.current, { type: 'audio/webm;codecs=opus' });
    
    // Only send if we have meaningful audio (at least 1KB)
    if (completeBlob.size < 1000) {
      audioChunksRef.current = [];
      return;
    }

    console.log(`Sending complete audio: ${completeBlob.size} bytes`);

    // Convert to base64 and send
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1];
      wsRef.current?.send(JSON.stringify({ type: 'audio', data: base64 }));
    };
    reader.readAsDataURL(completeBlob);

    // Clear the buffer
    audioChunksRef.current = [];
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      // Clear any previous chunks
      audioChunksRef.current = [];
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 48000,
        } 
      });
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });
      mediaRecorderRef.current = mediaRecorder;

      // NEW: Store chunks locally instead of sending
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Record in smaller chunks for smoother buffering
      mediaRecorder.start(500);
      setIsRecording(true);
    } catch (err) {
      setError('Microphone access denied');
    }
  }, []);

  // Stop recording and send accumulated audio
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      
      // Wait a moment for final chunk, then send
      setTimeout(() => {
        sendAccumulatedAudio();
      }, 100);
    }
    setIsRecording(false);
  }, [sendAccumulatedAudio]);

  // Toggle recording (push-to-talk style)
  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Format duration
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-zinc-900 rounded-2xl p-8 max-w-md w-full mx-4 border border-amber-500/20">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white mb-2">{assistantName}</h2>
          {isConnected && (
            <p className="text-amber-500 font-mono">{formatDuration(callDuration)}</p>
          )}
        </div>

        {/* Status indicators */}
        <div className="flex justify-center gap-4 mb-8">
          {isSpeaking && (
            <div className="flex items-center gap-2 text-amber-500">
              <Volume2 className="w-5 h-5 animate-pulse" />
              <span>Speaking...</span>
            </div>
          )}
          {isRecording && (
            <div className="flex items-center gap-2 text-red-500">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <span>Recording...</span>
            </div>
          )}
        </div>

        {/* Transcript */}
        <div className="bg-black/50 rounded-lg p-4 h-48 overflow-y-auto mb-8">
          {transcript.length === 0 ? (
            <p className="text-zinc-500 text-center">
              {isConnected ? 'Hold the mic button to speak...' : 'Press call to start'}
            </p>
          ) : (
            transcript.map((msg, i) => (
              <div
                key={i}
                className={`mb-2 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                <span
                  className={`inline-block px-3 py-2 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-amber-500/20 text-amber-200'
                      : 'bg-zinc-800 text-white'
                  }`}
                >
                  {msg.content}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/20 text-red-400 px-4 py-2 rounded-lg mb-4 text-center">
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="flex justify-center gap-4">
          {!isConnected ? (
            <button
              onClick={connect}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-full transition-colors"
            >
              <Phone className="w-5 h-5" />
              Start Call
            </button>
          ) : (
            <>
              {/* Push-to-talk mic button */}
              <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onMouseLeave={stopRecording}
                onTouchStart={startRecording}
                onTouchEnd={stopRecording}
                disabled={isSpeaking}
                className={`p-6 rounded-full transition-all ${
                  isRecording
                    ? 'bg-red-600 scale-110'
                    : isSpeaking
                    ? 'bg-zinc-700 cursor-not-allowed'
                    : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                {isRecording ? (
                  <MicOff className="w-8 h-8 text-white" />
                ) : (
                  <Mic className="w-8 h-8 text-white" />
                )}
              </button>

              {/* End call */}
              <button
                onClick={() => {
                  disconnect();
                  onClose();
                }}
                className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-full transition-colors"
              >
                <PhoneOff className="w-5 h-5" />
                End
              </button>
            </>
          )}
        </div>

        {/* Instructions */}
        {isConnected && (
          <p className="text-zinc-500 text-sm text-center mt-4">
            Hold the microphone button while speaking, release to send
          </p>
        )}

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-500 hover:text-white"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
