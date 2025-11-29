'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/lib/auth-context';

interface VoiceClone {
  id: string;
  voice_name: string;
  display_name: string;
  reference_audio_url: string;
  sample_duration: number | null;
  is_public: boolean;
  created_at: string;
}

interface UsageLimits {
  voice_clones_count: number;
  max_voice_clones: number;
}

export default function VoiceClonesPage() {
  const { user } = useAuth();
  const [voiceClones, setVoiceClones] = useState<VoiceClone[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [usageLimits, setUsageLimits] = useState<UsageLimits | null>(null);

  // Form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [voiceName, setVoiceName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);

  // Audio refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const audioPreviewRef = useRef<HTMLAudioElement | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [playingCloneId, setPlayingCloneId] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';

  const fetchVoiceClones = useCallback(async () => {
    if (!user) return;

    try {
      const response = await fetch(`${apiUrl}/voice-clones`, {
        headers: {
          'X-User-ID': user.id,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch voice clones');

      const data = await response.json();
      setVoiceClones(data.voice_clones || []);
    } catch (err) {
      console.error('Error fetching voice clones:', err);
      setError('Failed to load voice clones');
    }
  }, [user, apiUrl]);

  const fetchUsageLimits = useCallback(async () => {
    if (!user) return;

    try {
      const [usageRes, limitsRes] = await Promise.all([
        fetch(`${apiUrl}/usage`, { headers: { 'X-User-ID': user.id } }),
        fetch(`${apiUrl}/limits`, { headers: { 'X-User-ID': user.id } }),
      ]);

      if (usageRes.ok && limitsRes.ok) {
        const usage = await usageRes.json();
        const limits = await limitsRes.json();
        setUsageLimits({
          voice_clones_count: usage.usage?.voice_clones_count || 0,
          max_voice_clones: limits.limits?.max_voice_clones || 0,
        });
      }
    } catch (err) {
      console.error('Error fetching usage limits:', err);
    }
  }, [user, apiUrl]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchVoiceClones(), fetchUsageLimits()]);
      setLoading(false);
    };
    loadData();
  }, [fetchVoiceClones, fetchUsageLimits]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setRecordedBlob(blob);
        setPreviewUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setRecordingDuration(0);

      recordingTimerRef.current = setInterval(() => {
        setRecordingDuration(d => d + 1);
      }, 1000);
    } catch (err) {
      console.error('Error starting recording:', err);
      setError('Failed to access microphone. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAudioFile(file);
      setRecordedBlob(null);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const clearAudio = () => {
    setAudioFile(null);
    setRecordedBlob(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  const handleCreateVoiceClone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    const audioSource = audioFile || recordedBlob;
    if (!audioSource) {
      setError('Please provide an audio sample');
      return;
    }

    if (!voiceName.trim() || !displayName.trim()) {
      setError('Please fill in all required fields');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('audio', audioSource, audioFile?.name || 'recording.webm');
      formData.append('voice_name', voiceName.toLowerCase().replace(/\s+/g, '_'));
      formData.append('display_name', displayName);
      formData.append('is_public', String(isPublic));

      const response = await fetch(`${apiUrl}/clone-voice`, {
        method: 'POST',
        headers: {
          'X-User-ID': user.id,
        },
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create voice clone');
      }

      setSuccess('Voice clone created successfully!');
      setShowCreateForm(false);
      setVoiceName('');
      setDisplayName('');
      setIsPublic(false);
      clearAudio();
      await fetchVoiceClones();
      await fetchUsageLimits();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create voice clone');
    } finally {
      setCreating(false);
    }
  };

  const playVoiceSample = (clone: VoiceClone) => {
    if (playingCloneId === clone.id) {
      audioPreviewRef.current?.pause();
      setPlayingCloneId(null);
      return;
    }

    if (audioPreviewRef.current) {
      audioPreviewRef.current.pause();
    }

    const audio = new Audio(clone.reference_audio_url);
    audioPreviewRef.current = audio;
    audio.onended = () => setPlayingCloneId(null);
    audio.play();
    setPlayingCloneId(clone.id);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const canCreateMore = usageLimits && (
    usageLimits.max_voice_clones === -1 ||
    usageLimits.voice_clones_count < usageLimits.max_voice_clones
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-gold text-xl">Loading voice clones...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gold mb-2">Voice Clones</h1>
          <p className="text-gray-400">
            Create custom voice clones for your AI assistants
          </p>
        </div>

        {usageLimits && (
          <div className="text-right">
            <div className="text-2xl font-bold text-gold">
              {usageLimits.voice_clones_count} / {usageLimits.max_voice_clones === -1 ? '∞' : usageLimits.max_voice_clones}
            </div>
            <div className="text-sm text-gray-400">Voice Clones Used</div>
          </div>
        )}
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-lg text-red-200">
          {error}
          <button onClick={() => setError(null)} className="float-right text-red-400 hover:text-red-200">
            ×
          </button>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-green-900/50 border border-green-500 rounded-lg text-green-200">
          {success}
          <button onClick={() => setSuccess(null)} className="float-right text-green-400 hover:text-green-200">
            ×
          </button>
        </div>
      )}

      {/* Create Button */}
      {!showCreateForm && (
        <button
          onClick={() => setShowCreateForm(true)}
          disabled={!canCreateMore}
          className={`mb-8 px-6 py-3 rounded-lg font-medium transition-colors ${
            canCreateMore
              ? 'bg-gold text-black hover:bg-gold/90'
              : 'bg-gray-700 text-gray-400 cursor-not-allowed'
          }`}
        >
          {canCreateMore ? '+ Create Voice Clone' : 'Voice Clone Limit Reached'}
        </button>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="mb-8 p-6 bg-oled-dark border border-gold/30 rounded-lg">
          <h2 className="text-xl font-bold text-gold mb-4">Create Voice Clone</h2>

          <form onSubmit={handleCreateVoiceClone} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gold mb-2">
                  Voice Name (internal)
                </label>
                <input
                  type="text"
                  value={voiceName}
                  onChange={(e) => setVoiceName(e.target.value)}
                  placeholder="my_custom_voice"
                  className="w-full px-4 py-3 bg-oled-black border border-gold/30 rounded-lg
                    text-white focus:outline-none focus:border-gold transition-colors"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  Used internally, no spaces (will be auto-formatted)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gold mb-2">
                  Display Name
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="My Custom Voice"
                  className="w-full px-4 py-3 bg-oled-black border border-gold/30 rounded-lg
                    text-white focus:outline-none focus:border-gold transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gold mb-2">
                Audio Sample
              </label>
              <p className="text-sm text-gray-400 mb-4">
                Record or upload 10-30 seconds of clear speech for best results.
              </p>

              <div className="flex flex-wrap gap-4">
                {/* Record Button */}
                <button
                  type="button"
                  onClick={isRecording ? stopRecording : startRecording}
                  className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                    isRecording
                      ? 'bg-red-600 text-white animate-pulse'
                      : 'bg-gold/20 text-gold border border-gold/30 hover:bg-gold/30'
                  }`}
                >
                  {isRecording ? (
                    <>
                      <span className="inline-block w-3 h-3 bg-white rounded-full mr-2 animate-pulse"></span>
                      Stop Recording ({formatDuration(recordingDuration)})
                    </>
                  ) : (
                    '🎤 Record Voice'
                  )}
                </button>

                {/* Upload Button */}
                <label className="px-6 py-3 bg-gold/20 text-gold border border-gold/30 rounded-lg
                  font-medium cursor-pointer hover:bg-gold/30 transition-colors">
                  📁 Upload Audio
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>

                {/* Preview */}
                {previewUrl && (
                  <div className="flex items-center gap-4">
                    <audio src={previewUrl} controls className="h-10" />
                    <button
                      type="button"
                      onClick={clearAudio}
                      className="text-red-400 hover:text-red-300"
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              {recordedBlob && (
                <p className="text-sm text-green-400 mt-2">
                  Recording captured: {formatDuration(recordingDuration)}
                </p>
              )}

              {audioFile && (
                <p className="text-sm text-green-400 mt-2">
                  File selected: {audioFile.name}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="isPublic"
                checked={isPublic}
                onChange={(e) => setIsPublic(e.target.checked)}
                className="w-4 h-4 rounded border-gold/30 bg-oled-black text-gold focus:ring-gold"
              />
              <label htmlFor="isPublic" className="text-sm text-gray-300">
                Make this voice clone public (others can use it)
              </label>
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={creating || (!audioFile && !recordedBlob)}
                className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                  creating || (!audioFile && !recordedBlob)
                    ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                    : 'bg-gold text-black hover:bg-gold/90'
                }`}
              >
                {creating ? 'Creating Voice Clone...' : 'Create Voice Clone'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  clearAudio();
                }}
                className="px-6 py-3 bg-transparent border border-gold/30 text-gold
                  rounded-lg font-medium hover:bg-gold/10 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Voice Clones Grid */}
      {voiceClones.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🎙️</div>
          <h3 className="text-xl font-medium text-white mb-2">No Voice Clones Yet</h3>
          <p className="text-gray-400 mb-6">
            Create your first voice clone to use with your AI assistants
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {voiceClones.map((clone) => (
            <div
              key={clone.id}
              className="p-6 bg-oled-dark border border-gold/30 rounded-lg hover:border-gold/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-medium text-white">{clone.display_name}</h3>
                  <p className="text-sm text-gray-500">{clone.voice_name}</p>
                </div>
                {clone.is_public && (
                  <span className="px-2 py-1 text-xs bg-gold/20 text-gold rounded">
                    Public
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between">
                <button
                  onClick={() => playVoiceSample(clone)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                    playingCloneId === clone.id
                      ? 'bg-gold text-black'
                      : 'bg-gold/20 text-gold hover:bg-gold/30'
                  }`}
                >
                  {playingCloneId === clone.id ? (
                    <>⏹️ Stop</>
                  ) : (
                    <>▶️ Play Sample</>
                  )}
                </button>

                <span className="text-sm text-gray-500">
                  {new Date(clone.created_at).toLocaleDateString()}
                </span>
              </div>

              {clone.sample_duration && (
                <p className="text-xs text-gray-500 mt-2">
                  Duration: {formatDuration(Math.round(clone.sample_duration))}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Info Section */}
      <div className="mt-12 p-6 bg-oled-dark border border-gold/30 rounded-lg">
        <h3 className="text-lg font-medium text-gold mb-4">Tips for Great Voice Clones</h3>
        <ul className="space-y-2 text-gray-300">
          <li className="flex items-start gap-2">
            <span className="text-gold">•</span>
            Use a quiet environment with minimal background noise
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold">•</span>
            Record 15-30 seconds of natural speech for best results
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold">•</span>
            Speak clearly at a consistent pace and volume
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold">•</span>
            Use a good quality microphone if available
          </li>
          <li className="flex items-start gap-2">
            <span className="text-gold">•</span>
            Include a variety of sentences to capture natural speech patterns
          </li>
        </ul>
      </div>
    </div>
  );
}
