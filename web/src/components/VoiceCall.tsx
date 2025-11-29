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
  status: 'lightning' | 'fast' | 'good' | 'normal' | 'warning' | 'slow';
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

interface ErrorDetails {
  message: string;
  code?: string;
  timestamp: Date;
  context?: string;
  callId?: string;
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
  const [errorDetails, setErrorDetails] = useState<ErrorDetails | null>(null);
  const [errorHistory, setErrorHistory] = useState<ErrorDetails[]>([]);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [reportSubmitted, setReportSubmitted] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [callId, setCallId] = useState<string | null>(null);
  const [pipelineInfo, setPipelineInfo] = useState<string | null>(null);

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
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
    const wsUrl = apiUrl.replace(/^http/, 'ws');
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
          setErrorDetails(null);
          if (data.call_id) setCallId(data.call_id);
          // Auto-start audio streaming when connected
          startAudioStream();
          // Start call timer
          callTimerRef.current = setInterval(() => {
            setCallDuration(d => d + 1);
          }, 1000);
          break;
        case 'info':
          // Pipeline info (e.g., "Lightning pipeline active")
          if (data.message) setPipelineInfo(data.message);
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
          trackError(data.message, data.code, data.context);
          break;
        case 'warning':
          // Track warnings but don't show as main error
          setErrorHistory(prev => [...prev, {
            message: data.message,
            code: 'WARNING',
            timestamp: new Date(),
            context: data.context,
            callId: callId || undefined,
          }]);
          break;
        case 'call_ended':
          if (data.quality_score) {
            setQualityScore(data.quality_score);
          }
          setCallState('ended');
          break;
      }
    };

    ws.onerror = (e) => {
      trackError('Connection error', 'WS_ERROR', 'WebSocket connection failed');
    };
    ws.onclose = (e) => {
      if (callState === 'active') {
        if (e.code !== 1000) {
          trackError(`Connection closed unexpectedly (code: ${e.code})`, 'WS_CLOSE', e.reason || 'No reason provided');
        }
        setCallState('ended');
      }
    };
  }, [assistantId, userId, playNextAudio, startAudioStream, callState, trackError, callId]);

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
      case 'lightning': return 'text-cyan-400';  // ⚡ Sub-150ms
      case 'fast': return 'text-green-400';      // Sub-500ms
      case 'good': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      case 'normal': return 'text-yellow-400';
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

  // Track error with details
  const trackError = useCallback((message: string, code?: string, context?: string) => {
    const details: ErrorDetails = {
      message,
      code,
      timestamp: new Date(),
      context,
      callId: callId || undefined,
    };
    setError(message);
    setErrorDetails(details);
    setErrorHistory(prev => [...prev, details]);
    console.error('[VoiceCall Error]', details);
  }, [callId]);

  // Submit error report to backend
  const submitErrorReport = useCallback(async (additionalNotes?: string) => {
    setReportSubmitting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/error-reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          assistant_id: assistantId,
          call_id: callId,
          error_message: errorDetails?.message || error,
          error_code: errorDetails?.code,
          error_context: errorDetails?.context,
          error_history: errorHistory,
          pipeline_info: pipelineInfo,
          latency_data: latency,
          transcript_summary: transcript.slice(-5).map(t => `${t.role}: ${t.content.substring(0, 50)}`),
          call_duration: callDuration,
          user_notes: additionalNotes,
          user_agent: navigator.userAgent,
          timestamp: new Date().toISOString(),
        }),
      });

      if (response.ok) {
        setReportSubmitted(true);
        setTimeout(() => {
          setShowReportModal(false);
          setReportSubmitted(false);
        }, 2000);
      } else {
        throw new Error('Failed to submit report');
      }
    } catch (err) {
      console.error('Failed to submit error report:', err);
      alert('Failed to submit report. Please try again.');
    } finally {
      setReportSubmitting(false);
    }
  }, [userId, assistantId, callId, errorDetails, error, errorHistory, pipelineInfo, latency, transcript, callDuration]);

  // Call Summary Screen
  if (callState === 'ended') {
    return (
      <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
        {/* Header */}
        <div className="p-4 flex items-center justify-between border-b border-zinc-800">
          <span className="text-zinc-400 text-sm">Call Ended</span>
          <button onClick={onClose} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Summary Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-6">
          {qualityScore ? (
            <>
              <div className={`w-20 h-20 rounded-full border-4 flex items-center justify-center mb-4 ${getGradeColor(qualityScore.grade)}`}>
                <span className="text-3xl font-bold">{qualityScore.grade}</span>
              </div>
              <div className="text-center mb-4">
                <span className="text-3xl font-bold text-white">{qualityScore.total}</span>
                <span className="text-zinc-400 text-lg">/100</span>
              </div>
              <div className="text-zinc-400 mb-6 text-sm">
                {formatDuration(qualityScore.factors.duration_seconds)} • {qualityScore.factors.exchanges} exchanges
              </div>

              {/* Score Breakdown */}
              <div className="w-full space-y-2 mb-6">
                {Object.entries(qualityScore.breakdown).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-xs text-zinc-400 capitalize">{key.replace('_', ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full"
                          style={{ width: `${(value / 30) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500 w-5 text-right">{value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="w-16 h-16 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg text-white mb-2">Call Complete</h2>
              <p className="text-zinc-400">{formatDuration(callDuration)}</p>
            </>
          )}
        </div>

        {/* Done Button */}
        <div className="p-4 border-t border-zinc-800">
          <button
            onClick={onClose}
            className="w-full py-3 bg-amber-500 hover:bg-amber-600 text-black font-semibold rounded-xl transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  // Active Call Screen - Side Panel
  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-96 bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col z-50">
      {/* Header */}
      <div className="p-4 flex items-center justify-between border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center ${
            isAssistantSpeaking ? 'ring-2 ring-amber-400 ring-opacity-60' : ''
          }`}>
            <span className="text-lg font-bold text-black">
              {assistantName.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">{assistantName}</h1>
            <p className="text-xs text-zinc-400 font-mono">
              {callState === 'connecting' ? 'Connecting...' : formatDuration(callDuration)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {callState === 'active' && latency && (
            <span className={`text-xs font-mono flex items-center gap-1 ${getLatencyColor(latency.status)}`}>
              {latency.status === 'lightning' && <span>⚡</span>}
              {latency.total_ms}ms
            </span>
          )}
          <button onClick={endCall} className="text-zinc-400 hover:text-white p-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Sentiment & Status Bar */}
      {callState === 'active' && (
        <div className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between text-xs">
          {sentiment ? (
            <div className="flex items-center gap-2 text-zinc-400">
              <span>{getSentimentEmoji(sentiment.sentiment)}</span>
              <span className="capitalize">{sentiment.sentiment}</span>
              {sentiment.urgency !== 'normal' && (
                <span className={`px-1.5 py-0.5 rounded text-xs ${
                  sentiment.urgency === 'urgent' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {sentiment.urgency}
                </span>
              )}
            </div>
          ) : (
            <div className="text-zinc-500">Ready</div>
          )}
          <div className="flex items-center gap-2">
            {isSpeaking && <span className="text-green-400">● Listening</span>}
            {isAssistantSpeaking && <span className="text-amber-400">● Speaking</span>}
          </div>
        </div>
      )}

      {/* Error Display with Report Button */}
      {error && (
        <div className="mx-4 mt-3 bg-red-500/20 border border-red-500/50 rounded-lg overflow-hidden">
          <div className="px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 text-red-400 text-xs font-medium">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Error</span>
                  {errorDetails?.code && (
                    <span className="text-red-500/70">({errorDetails.code})</span>
                  )}
                </div>
                <p className="text-red-300 text-xs mt-1">{error}</p>
                {errorDetails?.context && (
                  <p className="text-red-400/60 text-xs mt-0.5">{errorDetails.context}</p>
                )}
              </div>
              <button
                onClick={() => setShowReportModal(true)}
                className="flex items-center gap-1 px-2 py-1 bg-red-500/30 hover:bg-red-500/50 rounded text-red-300 text-xs transition-colors shrink-0"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Report
              </button>
            </div>
          </div>
          {errorHistory.length > 1 && (
            <div className="px-3 py-1.5 bg-red-500/10 border-t border-red-500/30">
              <span className="text-red-400/70 text-xs">
                {errorHistory.length} issues detected during this call
              </span>
            </div>
          )}
        </div>
      )}

      {/* Report Issue Modal */}
      {showReportModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[60] p-4">
          <div className="bg-zinc-900 rounded-xl border border-zinc-700 w-full max-w-md shadow-2xl">
            <div className="p-4 border-b border-zinc-700">
              <div className="flex items-center justify-between">
                <h3 className="text-white font-semibold">Report Issue</h3>
                <button
                  onClick={() => setShowReportModal(false)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {reportSubmitted ? (
              <div className="p-6 text-center">
                <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-white font-medium">Report Submitted</p>
                <p className="text-zinc-400 text-sm mt-1">Thank you for helping us improve!</p>
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  submitErrorReport(formData.get('notes') as string);
                }}
              >
                <div className="p-4 space-y-4">
                  {/* Error Summary */}
                  <div className="bg-zinc-800 rounded-lg p-3">
                    <p className="text-xs text-zinc-400 mb-1">Error Details</p>
                    <p className="text-sm text-white">{error}</p>
                    {errorDetails?.code && (
                      <p className="text-xs text-zinc-500 mt-1">Code: {errorDetails.code}</p>
                    )}
                    {pipelineInfo && (
                      <p className="text-xs text-zinc-500 mt-1">Pipeline: {pipelineInfo}</p>
                    )}
                  </div>

                  {/* Technical Info */}
                  <div className="bg-zinc-800/50 rounded-lg p-3 text-xs text-zinc-500 space-y-1">
                    <p>Call ID: {callId || 'N/A'}</p>
                    <p>Duration: {formatDuration(callDuration)}</p>
                    <p>Latency: {latency ? `${latency.total_ms}ms (${latency.status})` : 'N/A'}</p>
                    <p>Errors in session: {errorHistory.length}</p>
                  </div>

                  {/* User Notes */}
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                      Additional details (optional)
                    </label>
                    <textarea
                      name="notes"
                      rows={3}
                      placeholder="Describe what you were doing when this error occurred..."
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500"
                    />
                  </div>
                </div>

                <div className="p-4 border-t border-zinc-700 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowReportModal(false)}
                    className="flex-1 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reportSubmitting}
                    className="flex-1 py-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-500/50 text-black font-medium rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    {reportSubmitting ? (
                      <>
                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Submitting...
                      </>
                    ) : (
                      'Submit Report'
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Transcript - Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 && callState === 'active' && (
          <div className="text-center text-zinc-500 text-sm py-8">
            Start speaking to begin the conversation...
          </div>
        )}
        {transcript.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm ${
              msg.role === 'user'
                ? 'bg-amber-500 text-black rounded-br-sm'
                : 'bg-zinc-800 text-white rounded-bl-sm'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Audio Level Indicator */}
      {callState === 'active' && (
        <div className="px-4 py-2 border-t border-zinc-800">
          <div className="flex items-center gap-0.5 h-6 justify-center">
            {[...Array(30)].map((_, i) => (
              <div
                key={i}
                className={`w-1 rounded-full transition-all duration-75 ${
                  isMuted ? 'bg-zinc-700' :
                  i < audioLevel / 3.3 ? (isSpeaking ? 'bg-green-400' : 'bg-zinc-600') : 'bg-zinc-800'
                }`}
                style={{
                  height: `${Math.max(4, Math.sin((i / 30) * Math.PI) * 24)}px`
                }}
              />
            ))}
          </div>
        </div>
      )}

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
