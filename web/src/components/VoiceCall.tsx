'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { HoneycombButton } from './HoneycombButton';

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
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [streamingMode, setStreamingMode] = useState(true);  // Default to streaming PCM for Deepgram

  // Real-time sentiment state
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  // Real-time latency state
  const [latency, setLatency] = useState<LatencyData | null>(null);
  // Call quality score (shown after call ends)
  const [qualityScore, setQualityScore] = useState<QualityScoreData | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

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
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://web-production-1b085.up.railway.app';
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
        case 'sentiment': setSentiment(data.data); break;
        case 'latency': setLatency(data.data); break;
        case 'info':
          // Check if streaming mode is active
          if (data.message?.includes('Streaming pipeline active')) {
            setStreamingMode(true);
          }
          break;
        case 'error': setError(data.message); break;
        case 'call_ended':
          if (data.quality_score) {
            setQualityScore(data.quality_score);
            setShowSummary(true);
          }
          setIsConnected(false);
          setIsRecording(false);
          break;
      }
    };
    ws.onerror = () => setError('Connection error');
    ws.onclose = () => setIsConnected(false);
  }, [assistantId, userId, playNextAudio]);

  const stopRecording = useCallback(() => {
    // Stop ScriptProcessor streaming
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    // Stop MediaRecorder (batch mode)
    if (mediaRecorderRef.current?.state !== 'inactive') {
      mediaRecorderRef.current?.stop();
    }
    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
    }
    stopRecording();
    setIsConnected(false);
  }, [stopRecording]);

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

  const startStreamingRecording = useCallback(async () => {
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

      // Use ScriptProcessorNode for raw PCM (deprecated but widely supported)
      // Buffer size: 4096 samples at 16kHz = 256ms chunks
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        // Downsample if needed (AudioContext might not honor sampleRate request)
        const downsampled = downsampleBuffer(inputData, audioContext.sampleRate, 16000);
        const pcmBuffer = floatTo16BitPCM(downsampled);

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
          format: 'pcm_16000'  // Tell backend this is raw PCM
        }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsRecording(true);
      console.log('Started streaming PCM audio capture');
    } catch (err) {
      console.error('Failed to start streaming recording:', err);
      setError('Microphone access denied');
    }
  }, []);

  const startBatchRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      streamRef.current = stream;

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

      mediaRecorder.start(3000);  // 3 second chunks for batch processing
      setIsRecording(true);
      console.log('Started batch audio recording (webm/opus)');
    } catch (err) {
      console.error('Failed to start batch recording:', err);
      setError('Microphone access denied');
    }
  }, []);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      stopRecording();
    } else {
      // Use streaming PCM for Deepgram, batch webm for Modal fallback
      // For now, always use batch until backend signals streaming is ready
      // The backend will check the 'format' field to know which mode
      if (streamingMode) {
        await startStreamingRecording();
      } else {
        await startBatchRecording();
      }
    }
  }, [isRecording, streamingMode, stopRecording, startStreamingRecording, startBatchRecording]);

  useEffect(() => { return () => { disconnect(); }; }, [disconnect]);

  // Helper functions for sentiment display
  const getSentimentColor = (s: string) => {
    switch (s) {
      case 'positive': return 'text-green-400 bg-green-500/20';
      case 'negative': return 'text-red-400 bg-red-500/20';
      default: return 'text-zinc-400 bg-zinc-500/20';
    }
  };

  const getSentimentEmoji = (s: string) => {
    switch (s) {
      case 'positive': return '😊';
      case 'negative': return '😟';
      default: return '😐';
    }
  };

  const getUrgencyColor = (u: string) => {
    switch (u) {
      case 'urgent': return 'text-red-400 bg-red-500/20 animate-pulse';
      case 'elevated': return 'text-yellow-400 bg-yellow-500/20';
      default: return 'text-zinc-400 bg-zinc-500/20';
    }
  };

  const getLatencyColor = (status: string) => {
    switch (status) {
      case 'good': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      default: return 'text-red-400';
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving': return '↗';
      case 'declining': return '↘';
      default: return '→';
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

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Call Summary Modal
  if (showSummary && qualityScore) {
    return (
      <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
        <div className="bg-zinc-900 border border-amber-500/30 rounded-lg p-6 max-w-md w-full mx-4">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-amber-500 mb-2">Call Complete</h2>
            <p className="text-zinc-400 text-sm">Here's how the call went</p>
          </div>

          {/* Quality Grade - Big Display */}
          <div className="flex justify-center mb-6">
            <div className={`w-24 h-24 rounded-full border-4 flex items-center justify-center ${getGradeColor(qualityScore.grade)}`}>
              <span className="text-4xl font-bold">{qualityScore.grade}</span>
            </div>
          </div>

          {/* Score */}
          <div className="text-center mb-6">
            <span className="text-3xl font-bold text-white">{qualityScore.total}</span>
            <span className="text-zinc-400">/100</span>
          </div>

          {/* Score Breakdown */}
          <div className="space-y-2 mb-6">
            <div className="text-xs text-zinc-400 mb-2">Score Breakdown</div>
            {Object.entries(qualityScore.breakdown).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm text-zinc-300 capitalize">{key.replace('_', ' ')}</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full"
                      style={{ width: `${(value / (key === 'sentiment' ? 30 : key === 'flow' ? 25 : key === 'duration' ? 20 : key === 'resolution' ? 15 : 10)) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-zinc-400 w-8 text-right">{value}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Call Stats */}
          <div className="grid grid-cols-3 gap-4 p-3 bg-black/50 rounded-lg mb-6">
            <div className="text-center">
              <div className="text-lg font-bold text-white">{formatDuration(qualityScore.factors.duration_seconds)}</div>
              <div className="text-xs text-zinc-500">Duration</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-white">{qualityScore.factors.exchanges}</div>
              <div className="text-xs text-zinc-500">Exchanges</div>
            </div>
            <div className="text-center">
              <div className={`text-lg font-bold capitalize ${
                qualityScore.factors.sentiment === 'positive' ? 'text-green-400' :
                qualityScore.factors.sentiment === 'negative' ? 'text-red-400' : 'text-zinc-400'
              }`}>
                {qualityScore.factors.sentiment}
              </div>
              <div className="text-xs text-zinc-500">Sentiment</div>
            </div>
          </div>

          <HoneycombButton onClick={onClose} variant="solid" className="w-full">
            Done
          </HoneycombButton>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-amber-500/30 rounded-lg p-6 max-w-2xl w-full mx-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-amber-500">{assistantName}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white text-2xl">&times;</button>
        </div>

        {/* Status Bar with Connection, Speaking, Sentiment, Urgency */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-zinc-400 text-sm">{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          {isSpeaking && <span className="text-amber-500 text-sm animate-pulse">Speaking...</span>}

          {/* Real-time Sentiment Indicator */}
          {sentiment && (
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${getSentimentColor(sentiment.sentiment)}`}>
              <span>{getSentimentEmoji(sentiment.sentiment)}</span>
              <span className="capitalize">{sentiment.sentiment}</span>
              <span className="opacity-60">{getTrendIcon(sentiment.trend)}</span>
            </div>
          )}

          {/* Urgency Indicator */}
          {sentiment && sentiment.urgency !== 'normal' && (
            <div className={`px-2 py-1 rounded text-xs font-semibold ${getUrgencyColor(sentiment.urgency)}`}>
              {sentiment.urgency === 'urgent' ? '🚨 URGENT' : '⚡ Elevated'}
            </div>
          )}
        </div>

        {/* Real-time Latency Display */}
        {latency && isConnected && (
          <div className="mb-4 p-3 bg-black/50 rounded-lg">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Response Time</span>
              <span className={`font-mono font-bold ${getLatencyColor(latency.status)}`}>
                {latency.total_ms}ms
                {latency.status === 'good' && ' ✓'}
                {latency.status === 'slow' && ' ⚠'}
              </span>
            </div>
            <div className="flex gap-4 mt-2 text-xs text-zinc-500">
              <span>STT: {latency.stt_ms}ms</span>
              <span>AI: {latency.llm_ms}ms</span>
              <span>TTS: {latency.tts_ms}ms</span>
            </div>
            {/* Latency bar visualization */}
            <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  latency.status === 'good' ? 'bg-green-500' :
                  latency.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, (latency.total_ms / latency.target_ms) * 50)}%` }}
              />
            </div>
          </div>
        )}

        {error && <div className="bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-2 rounded mb-4">{error}</div>}

        {/* Transcript */}
        <div className="bg-black/50 rounded-lg p-4 h-64 overflow-y-auto mb-4">
          {transcript.length === 0 ? (
            <p className="text-zinc-500 text-center">Start speaking to begin...</p>
          ) : transcript.map((msg, i) => (
            <div key={i} className={`mb-2 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
              <span className={`inline-block px-3 py-1 rounded-lg ${msg.role === 'user' ? 'bg-amber-500/20 text-amber-200' : 'bg-zinc-700 text-white'}`}>{msg.content}</span>
            </div>
          ))}
        </div>

        {/* Sentiment Score Bar (when available) */}
        {sentiment && (
          <div className="mb-4">
            <div className="flex justify-between text-xs text-zinc-500 mb-1">
              <span>Negative</span>
              <span>Sentiment Score: {sentiment.score}</span>
              <span>Positive</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden relative">
              {/* Center marker */}
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-zinc-600" />
              {/* Score indicator */}
              <div
                className={`absolute top-0 bottom-0 w-2 rounded-full transition-all duration-300 ${
                  sentiment.sentiment === 'positive' ? 'bg-green-500' :
                  sentiment.sentiment === 'negative' ? 'bg-red-500' : 'bg-zinc-500'
                }`}
                style={{ left: `${Math.max(0, Math.min(98, 50 + sentiment.score / 2))}%` }}
              />
            </div>
          </div>
        )}

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
      </div>
    </div>
  );
}