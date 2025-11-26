'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { HoneycombButton } from './HoneycombButton';

interface TranscriptMessage {
  role: 'user' | 'assistant';
  content: string;
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

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);

  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
    isPlayingRef.current = true;
    const audioBase64 = audioQueueRef.current.shift()!;
    try {
      if (!audioContextRef.current) audioContextRef.current = new AudioContext();
      const audioData = atob(audioBase64);
      const arrayBuffer = new ArrayBuffer(audioData.length);
      const view = new Uint8Array(arrayBuffer);
      for (let i = 0; i < audioData.length; i++) view[i] = audioData.charCodeAt(i);
      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.onended = () => { isPlayingRef.current = false; playNextAudio(); };
      source.start();
    } catch (err) {
      console.error('Audio playback error:', err);
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, []);

  const connect = useCallback(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8080';
    const wsUrl = backendUrl.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsUrl}/ws/voice/${assistantId}`);
    wsRef.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', user_id: userId }));
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case 'ready': setIsConnected(true); setError(null); break;
        case 'transcript': setTranscript(prev => [...prev, { role: data.role, content: data.content }]); break;
        case 'audio': audioQueueRef.current.push(data.data); playNextAudio(); break;
        case 'speaking': setIsSpeaking(data.is_speaking); break;
        case 'error': setError(data.message); break;
        case 'call_ended': disconnect(); break;
      }
    };
    ws.onerror = () => setError('Connection error');
    ws.onclose = () => setIsConnected(false);
  }, [assistantId, userId, playNextAudio]);

  const disconnect = useCallback(() => {
    if (wsRef.current) { wsRef.current.send(JSON.stringify({ type: 'end_call' })); wsRef.current.close(); }
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop();
    setIsConnected(false);
    setIsRecording(false);
  }, []);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
        mediaRecorderRef.current = mediaRecorder;
        mediaRecorder.ondataavailable = async (event) => {
          if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64 = (reader.result as string).split(',')[1];
              wsRef.current?.send(JSON.stringify({ type: 'audio', data: base64 }));
            };
            reader.readAsDataURL(event.data);
          }
        };
        mediaRecorder.start(3000);
        setIsRecording(true);
      } catch { setError('Microphone access denied'); }
    }
  }, [isRecording]);

  useEffect(() => { return () => { disconnect(); }; }, [disconnect]);

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-amber-500/30 rounded-lg p-6 max-w-lg w-full mx-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-amber-500">{assistantName}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white text-2xl">&times;</button>
        </div>
        <div className="flex items-center gap-2 mb-4">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-zinc-400">{isConnected ? 'Connected' : 'Disconnected'}</span>
          {isSpeaking && <span className="text-amber-500 ml-2">Speaking...</span>}
        </div>
        {error && <div className="bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-2 rounded mb-4">{error}</div>}
        <div className="bg-black/50 rounded-lg p-4 h-64 overflow-y-auto mb-4">
          {transcript.length === 0 ? (
            <p className="text-zinc-500 text-center">Start speaking to begin...</p>
          ) : transcript.map((msg, i) => (
            <div key={i} className={`mb-2 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
              <span className={`inline-block px-3 py-1 rounded-lg ${msg.role === 'user' ? 'bg-amber-500/20 text-amber-200' : 'bg-zinc-700 text-white'}`}>{msg.content}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-center gap-4">
          {!isConnected ? (
            <HoneycombButton onClick={connect} variant="solid">Start Call</HoneycombButton>
          ) : (
            <>
              <HoneycombButton onClick={toggleRecording} variant={isRecording ? 'outline' : 'solid'}>{isRecording ? 'Stop' : 'Record'}</HoneycombButton>
              <HoneycombButton onClick={disconnect} variant="outline">End Call</HoneycombButton>
            </>
          )}
        </div>
          )}
        </div>
      </div>
    </div>
  );
}