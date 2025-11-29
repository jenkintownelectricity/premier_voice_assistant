'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface TranscriptMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface SentimentData {
  sentiment: 'positive' | 'neutral' | 'negative';
  score: number;
  urgency: 'normal' | 'elevated' | 'urgent';
  trend: 'improving' | 'stable' | 'declining';
  positive_signals: number;
  negative_signals: number;
}

interface LatencyData {
  stt_ms: number;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
  target_ms: number;
  status: 'good' | 'warning' | 'slow';
}

interface QualityScoreData {
  total: number;
  grade: string;
  breakdown: {
    sentiment: number;
    flow: number;
    duration: number;
    resolution: number;
    urgency_handling: number;
  };
  factors: {
    sentiment: string;
    exchanges: number;
    duration_seconds: number;
    urgency: string;
  };
}

interface VoiceCallProps {
  assistantId: string;
  assistantName: string;
  userId: string;
  onClose: () => void;
}

export function VoiceCall({ assistantId, assistantName, userId, onClose }: VoiceCallProps) {
  const [callState, setCallState] = useState<'connecting' | 'active' | 'ended'>('connecting');
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isAssistantSpeaking, setIsAssistantSpeaking] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [callDuration, setCallDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);

  // Real-time sentiment state
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  // Real-time latency state
  const [latency, setLatency] = useState<LatencyData | null>(null);
  // Call quality score (shown after call ends)
  const [qualityScore, setQualityScore] = useState<QualityScoreData | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const callTimerRef = useRef<NodeJS.Timeout | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
    isPlayingRef.current = true;
    setIsAssistantSpeaking(true);
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
      source.onended = () => {
        isPlayingRef.current = false;
        if (audioQueueRef.current.length === 0) {
          setIsAssistantSpeaking(false);
        }
        playNextAudio();
      };
      source.start();
    } catch (err) {
      console.error('Audio playback error:', err);
      isPlayingRef.current = false;
      setIsAssistantSpeaking(false);
      playNextAudio();
    }
  }, []);

  // Convert Float32 audio samples to 16-bit PCM
  const floatTo16BitPCM = (float32Array: Float32Array): ArrayBuffer => {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
  };

  // Downsample from source sample rate to 16kHz
  const downsampleBuffer = (buffer: Float32Array, sampleRate: number, targetRate: number): Float32Array => {
    if (sampleRate === targetRate) return buffer;
    const sampleRateRatio = sampleRate / targetRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0, count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = accum / count;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  };

  // Start continuous audio streaming
  const startAudioStream = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      streamRef.current = stream;

      // Create AudioContext for raw PCM capture
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      // Create analyser for audio level visualization
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);

      // Use ScriptProcessorNode for raw PCM
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN || isMuted) return;

        const inputData = e.inputBuffer.getChannelData(0);
        const downsampled = downsampleBuffer(inputData, audioContext.sampleRate, 16000);
        const pcmBuffer = floatTo16BitPCM(downsampled);

        // Calculate RMS for speaking detection
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        const db = 20 * Math.log10(rms + 0.0001);
        const normalizedLevel = Math.max(0, Math.min(100, (db + 60) * 2));
        setAudioLevel(normalizedLevel);
        setIsSpeaking(normalizedLevel > 15);

        // Convert to base64 and send
        const bytes = new Uint8Array(pcmBuffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);

        wsRef.current?.send(JSON.stringify({
          type: 'audio',
          data: base64,
          format: 'pcm_16000'
        }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      console.log('Started continuous audio streaming');
    } catch (err) {
      console.error('Failed to start audio stream:', err);
      setError('Microphone access denied. Please allow microphone access to use voice calls.');
    }
  }, [isMuted]);

  const stopAudioStream = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (analyserRef.current) {
      analyserRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setAudioLevel(0);
    setIsSpeaking(false);
  }, []);

  const connect = useCallback(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://web-production-1b085.up.railway.app';
    const wsUrl = backendUrl.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsUrl}/ws/voice/${assistantId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', user_id: userId }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case 'ready':
          setCallState('active');
          setError(null);
          // Auto-start audio streaming when connected
          startAudioStream();
          // Start call timer
          callTimerRef.current = setInterval(() => {
            setCallDuration(d => d + 1);
          }, 1000);
          break;
        case 'transcript':
          setTranscript(prev => [...prev, { role: data.role, content: data.content }]);
          break;
        case 'audio':
          audioQueueRef.current.push(data.data);
          playNextAudio();
          break;
        case 'speaking':
          setIsAssistantSpeaking(data.is_speaking);
          break;
        case 'sentiment':
          setSentiment(data.data);
          break;
        case 'latency':
          setLatency(data.data);
          break;
        case 'error':
          setError(data.message);
          break;
        case 'call_ended':
          if (data.quality_score) {
            setQualityScore(data.quality_score);
          }
          setCallState('ended');
          break;
      }
    };

    ws.onerror = () => setError('Connection error');
    ws.onclose = () => {
      if (callState === 'active') {
        setCallState('ended');
      }
    };
  }, [assistantId, userId, playNextAudio, startAudioStream, callState]);

  const endCall = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
    }
    stopAudioStream();
    if (callTimerRef.current) {
      clearInterval(callTimerRef.current);
    }
    setCallState('ended');
  }, [stopAudioStream]);

  const toggleMute = useCallback(() => {
    setIsMuted(prev => !prev);
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach(track => {
        track.enabled = isMuted; // Toggle: if currently muted, enable; if not muted, disable
      });
    }
  }, [isMuted]);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      stopAudioStream();
      if (callTimerRef.current) {
        clearInterval(callTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getLatencyColor = (status: string) => {
    switch (status) {
      case 'good': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      default: return 'text-red-400';
    }
  };

  const getSentimentEmoji = (s: string) => {
    switch (s) {
      case 'positive': return '😊';
      case 'negative': return '😟';
      default: return '😐';
    }
  };

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-green-400 bg-green-500/20 border-green-500';
      case 'B': return 'text-blue-400 bg-blue-500/20 border-blue-500';
      case 'C': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500';
      case 'D': return 'text-orange-400 bg-orange-500/20 border-orange-500';
      default: return 'text-red-400 bg-red-500/20 border-red-500';
    }
  };

  // Call Summary Screen
  if (callState === 'ended') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-zinc-900 to-black flex flex-col">
        {/* Header */}
        <div className="p-4 flex items-center justify-between">
          <button onClick={onClose} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <span className="text-zinc-400 text-sm">Call Ended</span>
          <div className="w-10" />
        </div>

        {/* Summary Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          {qualityScore ? (
            <>
              <div className={`w-28 h-28 rounded-full border-4 flex items-center justify-center mb-4 ${getGradeColor(qualityScore.grade)}`}>
                <span className="text-5xl font-bold">{qualityScore.grade}</span>
              </div>
              <div className="text-center mb-6">
                <span className="text-4xl font-bold text-white">{qualityScore.total}</span>
                <span className="text-zinc-400 text-xl">/100</span>
              </div>
              <div className="text-zinc-400 mb-8">
                {formatDuration(qualityScore.factors.duration_seconds)} • {qualityScore.factors.exchanges} exchanges
              </div>

              {/* Score Breakdown */}
              <div className="w-full max-w-sm space-y-3 mb-8">
                {Object.entries(qualityScore.breakdown).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-sm text-zinc-400 capitalize">{key.replace('_', ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full"
                          style={{ width: `${(value / 30) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500 w-6 text-right">{value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
                <svg className="w-10 h-10 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xl text-white mb-2">Call Complete</h2>
              <p className="text-zinc-400">{formatDuration(callDuration)}</p>
            </>
          )}
        </div>

        {/* Done Button */}
        <div className="p-6">
          <button
            onClick={onClose}
            className="w-full py-4 bg-amber-500 hover:bg-amber-600 text-black font-semibold rounded-2xl transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  // Active Call Screen
  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-900 to-black flex flex-col">
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <button onClick={endCall} className="text-zinc-400 hover:text-white p-2">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          {callState === 'connecting' && (
            <span className="text-zinc-400 text-sm animate-pulse">Connecting...</span>
          )}
          {callState === 'active' && latency && (
            <span className={`text-xs font-mono ${getLatencyColor(latency.status)}`}>
              {latency.total_ms}ms
            </span>
          )}
        </div>
        <div className="w-10" />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center pt-8">
        {/* Avatar with Speaking Indicator */}
        <div className="relative mb-4">
          <div className={`w-32 h-32 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center transition-all duration-300 ${
            isAssistantSpeaking ? 'ring-4 ring-amber-400 ring-opacity-60 scale-105' : ''
          }`}>
            <span className="text-5xl font-bold text-black">
              {assistantName.charAt(0).toUpperCase()}
            </span>
          </div>
          {isAssistantSpeaking && (
            <div className="absolute -inset-2 rounded-full border-2 border-amber-400 animate-ping opacity-30" />
          )}
        </div>

        {/* Assistant Name */}
        <h1 className="text-2xl font-semibold text-white mb-1">{assistantName}</h1>

        {/* Call Duration */}
        <p className="text-zinc-400 text-lg font-mono mb-2">
          {callState === 'connecting' ? 'Connecting...' : formatDuration(callDuration)}
        </p>

        {/* Sentiment Indicator */}
        {sentiment && (
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <span>{getSentimentEmoji(sentiment.sentiment)}</span>
            <span className="capitalize">{sentiment.sentiment}</span>
            {sentiment.urgency !== 'normal' && (
              <span className={`px-2 py-0.5 rounded text-xs ${
                sentiment.urgency === 'urgent' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
              }`}>
                {sentiment.urgency}
              </span>
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mx-4 mt-4 bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-2 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Audio Level Indicator */}
        {callState === 'active' && (
          <div className="mt-6 flex items-center gap-1 h-12">
            {[...Array(20)].map((_, i) => (
              <div
                key={i}
                className={`w-1 rounded-full transition-all duration-75 ${
                  isMuted ? 'bg-zinc-700' :
                  i < audioLevel / 5 ? (isSpeaking ? 'bg-green-400' : 'bg-zinc-500') : 'bg-zinc-800'
                }`}
                style={{
                  height: `${Math.max(8, Math.sin((i / 20) * Math.PI) * 48)}px`
                }}
              />
            ))}
          </div>
        )}

        {/* Speaking Status */}
        {callState === 'active' && (
          <p className="text-sm text-zinc-500 mt-2">
            {isMuted ? 'Muted' : isSpeaking ? 'Listening...' : 'Speak anytime'}
          </p>
        )}

        {/* Transcript - Scrollable */}
        <div className="flex-1 w-full max-w-lg mt-6 px-4 overflow-y-auto">
          {transcript.map((msg, i) => (
            <div
              key={i}
              className={`mb-3 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                msg.role === 'user'
                  ? 'bg-amber-500 text-black rounded-br-sm'
                  : 'bg-zinc-800 text-white rounded-bl-sm'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Controls */}
      <div className="p-6 pb-10">
        <div className="flex items-center justify-center gap-8">
          {/* Mute Button */}
          <button
            onClick={toggleMute}
            className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
              isMuted
                ? 'bg-white text-black'
                : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            {isMuted ? (
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
              </svg>
            ) : (
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            )}
          </button>

          {/* End Call Button */}
          <button
            onClick={endCall}
            className="w-20 h-20 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors"
          >
            <svg className="w-9 h-9 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.28 3H5z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
