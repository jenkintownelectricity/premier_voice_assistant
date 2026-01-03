'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface Call {
  id: string;
  assistant_id: string | null;
  assistant_name: string;
  call_type: string;
  phone_number: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  cost_cents: number;
  summary: string | null;
  sentiment: string | null;
  ended_reason: string | null;
}

interface CallStats {
  total_calls: number;
  total_duration_seconds: number;
  total_cost_cents: number;
  avg_duration_seconds: number;
  completed_calls: number;
  failed_calls: number;
  calls_today: number;
  calls_this_week: number;
  calls_this_month: number;
}

interface CallDetail {
  id: string;
  assistant_id: string | null;
  assistant_name: string;
  call_type: string;
  phone_number: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  cost_cents: number;
  minutes_used: number;
  transcript: Array<{ role: string; content: string; timestamp?: string }> | null;
  summary: string | CallSummary | null;
  recording_url: string | null;
  sentiment: string | null;
  ended_reason: string | null;
}

interface CallSummary {
  quality_score?: number;
  quality_grade?: string;
  quality_breakdown?: {
    sentiment: number;
    flow: number;
    duration: number;
    resolution: number;
    urgency_handling: number;
  };
  sentiment_score?: number;
  urgency_level?: string;
  exchange_count?: number;
}

interface ExtractedInfo {
  callerName: string | null;
  phoneNumber: string | null;
  email: string | null;
  company: string | null;
  issue: string | null;
  urgency: 'low' | 'medium' | 'high' | null;
  actionItems: string[];
  appointmentDate: string | null;
  serviceType: string | null;
}

// Extract information from transcript using pattern matching
function extractInfoFromTranscript(transcript: Array<{ role: string; content: string }>): ExtractedInfo {
  const fullText = transcript.map(m => m.content).join(' ');
  const userMessages = transcript.filter(m => m.role === 'user').map(m => m.content).join(' ');

  // Extract phone number
  const phoneMatch = fullText.match(/(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})/);

  // Extract email
  const emailMatch = fullText.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);

  // Extract name patterns
  const namePatterns = [
    /(?:my name is|i'm|this is|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/i,
    /(?:name[:\s]+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/i,
  ];
  let callerName: string | null = null;
  for (const pattern of namePatterns) {
    const match = userMessages.match(pattern);
    if (match) {
      callerName = match[1];
      break;
    }
  }

  // Extract company
  const companyPatterns = [
    /(?:from|with|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:\s+(?:Inc|LLC|Corp|Company|Co))?)/i,
    /(?:company[:\s]+)([A-Z][a-zA-Z\s]+)/i,
  ];
  let company: string | null = null;
  for (const pattern of companyPatterns) {
    const match = userMessages.match(pattern);
    if (match) {
      company = match[1].trim();
      break;
    }
  }

  // Extract issue/problem
  const issuePatterns = [
    /(?:problem|issue|need help with|having trouble with|not working)\s*[:\s]*(.{10,100})/i,
    /(?:i need|i want|looking for|calling about)\s+(.{10,100})/i,
  ];
  let issue: string | null = null;
  for (const pattern of issuePatterns) {
    const match = userMessages.match(pattern);
    if (match) {
      issue = match[1].trim().replace(/[.!?].*$/, '');
      break;
    }
  }

  // Determine urgency based on keywords
  let urgency: 'low' | 'medium' | 'high' | null = null;
  const urgentKeywords = ['emergency', 'urgent', 'asap', 'immediately', 'right away', 'critical', 'dangerous', 'flooding', 'fire', 'sparking', 'smoke'];
  const mediumKeywords = ['soon', 'today', 'this week', 'important', 'broken', 'not working'];

  const lowerText = fullText.toLowerCase();
  if (urgentKeywords.some(k => lowerText.includes(k))) {
    urgency = 'high';
  } else if (mediumKeywords.some(k => lowerText.includes(k))) {
    urgency = 'medium';
  } else {
    urgency = 'low';
  }

  // Extract service type
  const serviceTypes = [
    'electrical', 'plumbing', 'hvac', 'heating', 'cooling', 'air conditioning',
    'outlet', 'switch', 'panel', 'wiring', 'circuit', 'breaker', 'generator',
    'water heater', 'furnace', 'thermostat', 'duct', 'leak', 'drain', 'pipe'
  ];
  let serviceType: string | null = null;
  for (const service of serviceTypes) {
    if (lowerText.includes(service)) {
      serviceType = service.charAt(0).toUpperCase() + service.slice(1);
      break;
    }
  }

  // Extract action items from assistant responses
  const actionItems: string[] = [];
  const assistantMessages = transcript.filter(m => m.role === 'assistant').map(m => m.content);
  const actionPatterns = [
    /(?:i'll|i will|we'll|we will|let me)\s+(.{10,80})/gi,
    /(?:scheduled|booked|confirmed)\s+(.{10,80})/gi,
    /(?:someone will)\s+(.{10,80})/gi,
  ];

  for (const msg of assistantMessages) {
    for (const pattern of actionPatterns) {
      const matches = Array.from(msg.matchAll(pattern));
      for (const match of matches) {
        const item = match[1].trim().replace(/[.!?].*$/, '');
        if (item.length > 5 && !actionItems.includes(item)) {
          actionItems.push(item);
        }
      }
    }
  }

  // Extract appointment date
  const datePatterns = [
    /(?:scheduled for|appointment on|come by on|booked for)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)/i,
    /(\d{1,2}\/\d{1,2}\/\d{2,4})/,
  ];
  let appointmentDate: string | null = null;
  for (const pattern of datePatterns) {
    const match = fullText.match(pattern);
    if (match) {
      appointmentDate = match[1];
      break;
    }
  }

  return {
    callerName,
    phoneNumber: phoneMatch ? phoneMatch[1] : null,
    email: emailMatch ? emailMatch[1] : null,
    company,
    issue,
    urgency,
    actionItems: actionItems.slice(0, 5), // Limit to 5 action items
    appointmentDate,
    serviceType,
  };
}

export default function CallsPage() {
  const { user } = useAuth();
  const [calls, setCalls] = useState<Call[]>([]);
  const [stats, setStats] = useState<CallStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<CallDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState<'overview' | 'transcript' | 'recording'>('overview');
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const limit = 20;

  // Extract info from selected call
  const extractedInfo = useMemo(() => {
    if (!selectedCall?.transcript) return null;
    return extractInfoFromTranscript(selectedCall.transcript);
  }, [selectedCall]);

  useEffect(() => {
    if (user?.id) {
      loadCalls();
      loadStats();
    }
  }, [user?.id, page]);

  const loadCalls = async () => {
    if (!user?.id) return;
    try {
      const response = await api.getCalls(user.id, limit, page * limit);
      setCalls(response.calls);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load calls:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    if (!user?.id) return;
    try {
      const response = await api.getCallStats(user.id);
      setStats(response.stats);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const loadCallDetail = async (callId: string) => {
    if (!user?.id) return;
    setLoadingDetail(true);
    setActiveTab('overview');
    try {
      const response = await api.getCall(user.id, callId);
      setSelectedCall(response.call);
    } catch (err) {
      console.error('Failed to load call detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeDetail = () => {
    setSelectedCall(null);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsPlaying(false);
    setAudioProgress(0);
  };

  // Audio playback controls
  const togglePlayback = () => {
    if (!selectedCall?.recording_url) return;

    if (!audioRef.current) {
      audioRef.current = new Audio(selectedCall.recording_url);
      audioRef.current.onloadedmetadata = () => {
        setAudioDuration(audioRef.current?.duration || 0);
      };
      audioRef.current.ontimeupdate = () => {
        setAudioProgress(audioRef.current?.currentTime || 0);
      };
      audioRef.current.onended = () => {
        setIsPlaying(false);
        setAudioProgress(0);
      };
    }

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const seekAudio = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setAudioProgress(time);
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatCost = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const formatFullDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400 bg-green-500/20';
      case 'failed': return 'text-red-400 bg-red-500/20';
      case 'in_progress': return 'text-yellow-400 bg-yellow-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getSentimentColor = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive': return 'text-green-400 bg-green-500/20';
      case 'negative': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getUrgencyColor = (urgency: string | null) => {
    switch (urgency) {
      case 'high': return 'text-red-400 bg-red-500/20 border-red-500/50';
      case 'medium': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/50';
      default: return 'text-green-400 bg-green-500/20 border-green-500/50';
    }
  };

  const exportCall = (format: 'json' | 'csv') => {
    if (!selectedCall) return;

    const data = {
      id: selectedCall.id,
      assistant: selectedCall.assistant_name,
      date: selectedCall.started_at,
      duration: formatDuration(selectedCall.duration_seconds),
      status: selectedCall.status,
      sentiment: selectedCall.sentiment,
      summary: selectedCall.summary,
      transcript: selectedCall.transcript,
      extractedInfo,
    };

    let content: string;
    let filename: string;
    let mimeType: string;

    if (format === 'json') {
      content = JSON.stringify(data, null, 2);
      filename = `call-${selectedCall.id}.json`;
      mimeType = 'application/json';
    } else {
      // Format transcript for CSV (combine all messages)
      const transcriptText = selectedCall.transcript && Array.isArray(selectedCall.transcript)
        ? selectedCall.transcript.map((t: { role: string; content: string }) =>
            `[${t.role}]: ${t.content}`
          ).join(' | ')
        : (typeof selectedCall.transcript === 'string' ? selectedCall.transcript : '');

      const rows = [
        ['Field', 'Value'],
        ['ID', selectedCall.id],
        ['Assistant', selectedCall.assistant_name],
        ['Date', selectedCall.started_at],
        ['Duration', formatDuration(selectedCall.duration_seconds)],
        ['Status', selectedCall.status],
        ['Sentiment', selectedCall.sentiment || ''],
        ['Caller Name', extractedInfo?.callerName || ''],
        ['Phone', extractedInfo?.phoneNumber || ''],
        ['Email', extractedInfo?.email || ''],
        ['Issue', extractedInfo?.issue || ''],
        ['Urgency', extractedInfo?.urgency || ''],
        ['Summary', typeof selectedCall.summary === 'string' ? selectedCall.summary : (selectedCall.summary ? `Score: ${selectedCall.summary.quality_score || 0}` : '')],
        ['Full Transcript', transcriptText.replace(/"/g, '""')],  // Escape quotes for CSV
      ];
      content = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
      filename = `call-${selectedCall.id}.csv`;
      mimeType = 'text/csv';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading call logs...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gold">Call Recordings</h1>
          <p className="text-gray-400 mt-1">
            View recordings, transcripts, and extracted information from your calls
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent>
              <div className="text-2xl font-bold text-gold">{stats.total_calls}</div>
              <div className="text-sm text-gray-400">Total Calls</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <div className="text-2xl font-bold text-gold">
                {formatDuration(stats.total_duration_seconds)}
              </div>
              <div className="text-sm text-gray-400">Total Duration</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <div className="text-2xl font-bold text-gold">
                {formatCost(stats.total_cost_cents)}
              </div>
              <div className="text-sm text-gray-400">Total Cost</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <div className="text-2xl font-bold text-green-400">{stats.completed_calls}</div>
              <div className="text-sm text-gray-400">Completed</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <div className="text-2xl font-bold text-gold">{stats.calls_today}</div>
              <div className="text-sm text-gray-400">Today</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Call Detail Modal - Full Width */}
      {selectedCall && (
        <div className="fixed inset-0 bg-black/80 z-50 overflow-y-auto">
          <div className="min-h-screen p-4 md:p-8">
            <div className="max-w-6xl mx-auto bg-zinc-900 rounded-xl border border-gold/20 overflow-hidden">
              {/* Modal Header */}
              <div className="flex justify-between items-center p-4 border-b border-gold/10 bg-zinc-800">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center">
                    <span className="text-xl font-bold text-black">
                      {selectedCall.assistant_name.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedCall.assistant_name}</h2>
                    <p className="text-sm text-gray-400">{formatFullDate(selectedCall.started_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => exportCall('json')}
                    className="px-3 py-1.5 text-sm bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors"
                  >
                    Export JSON
                  </button>
                  <button
                    onClick={() => exportCall('csv')}
                    className="px-3 py-1.5 text-sm bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors"
                  >
                    Export CSV
                  </button>
                  <button
                    onClick={closeDetail}
                    className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-zinc-700"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Quick Stats Bar */}
              <div className="flex items-center gap-6 p-4 bg-zinc-800/50 border-b border-gold/10">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-white font-medium">{formatDuration(selectedCall.duration_seconds)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${getStatusColor(selectedCall.status)}`}>
                    {selectedCall.status}
                  </span>
                </div>
                {selectedCall.sentiment && (
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${getSentimentColor(selectedCall.sentiment)}`}>
                      {selectedCall.sentiment}
                    </span>
                  </div>
                )}
                {extractedInfo?.urgency && (
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs border ${getUrgencyColor(extractedInfo.urgency)}`}>
                      {extractedInfo.urgency} urgency
                    </span>
                  </div>
                )}
                <div className="flex items-center gap-2 ml-auto">
                  <span className="text-gray-400 text-sm">Cost:</span>
                  <span className="text-white font-medium">{formatCost(selectedCall.cost_cents)}</span>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-gold/10">
                {[
                  { id: 'overview', label: 'Overview & Extracted Info' },
                  { id: 'transcript', label: 'Full Transcript' },
                  { id: 'recording', label: 'Recording' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as typeof activeTab)}
                    className={`px-6 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'text-gold border-b-2 border-gold bg-gold/5'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {/* Overview Tab */}
                {activeTab === 'overview' && (
                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Extracted Information */}
                    <div className="space-y-4">
                      <h3 className="text-lg font-semibold text-gold">Extracted Information</h3>

                      <div className="bg-zinc-800 rounded-lg p-4 space-y-3">
                        {extractedInfo?.callerName && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Caller Name</span>
                            <span className="text-white font-medium">{extractedInfo.callerName}</span>
                          </div>
                        )}
                        {extractedInfo?.phoneNumber && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Phone</span>
                            <span className="text-white font-medium">{extractedInfo.phoneNumber}</span>
                          </div>
                        )}
                        {extractedInfo?.email && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Email</span>
                            <span className="text-white font-medium">{extractedInfo.email}</span>
                          </div>
                        )}
                        {extractedInfo?.company && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Company</span>
                            <span className="text-white font-medium">{extractedInfo.company}</span>
                          </div>
                        )}
                        {extractedInfo?.serviceType && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Service Type</span>
                            <span className="text-white font-medium">{extractedInfo.serviceType}</span>
                          </div>
                        )}
                        {extractedInfo?.appointmentDate && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">Appointment</span>
                            <span className="text-white font-medium">{extractedInfo.appointmentDate}</span>
                          </div>
                        )}
                        {!extractedInfo?.callerName && !extractedInfo?.phoneNumber && !extractedInfo?.email && (
                          <p className="text-gray-500 text-sm">No contact information extracted from this call.</p>
                        )}
                      </div>

                      {/* Issue */}
                      {extractedInfo?.issue && (
                        <div className="bg-zinc-800 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-400 mb-2">Issue/Request</h4>
                          <p className="text-white">{extractedInfo.issue}</p>
                        </div>
                      )}

                      {/* Action Items */}
                      {extractedInfo?.actionItems && extractedInfo.actionItems.length > 0 && (
                        <div className="bg-zinc-800 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-gray-400 mb-2">Action Items</h4>
                          <ul className="space-y-2">
                            {extractedInfo.actionItems.map((item, idx) => (
                              <li key={idx} className="flex items-start gap-2 text-white">
                                <svg className="w-5 h-5 text-gold flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Summary & Details */}
                    <div className="space-y-4">
                      <h3 className="text-lg font-semibold text-gold">Call Summary</h3>

                      {selectedCall.summary ? (
                        <div className="bg-zinc-800 rounded-lg p-4">
                          {typeof selectedCall.summary === 'string' ? (
                            <p className="text-white leading-relaxed">{selectedCall.summary}</p>
                          ) : (
                            <div className="space-y-3">
                              {/* Quality Score Display */}
                              {selectedCall.summary.quality_score !== undefined && (
                                <div className="flex items-center gap-4">
                                  <div className={`w-16 h-16 rounded-full border-2 flex items-center justify-center ${
                                    selectedCall.summary.quality_grade === 'A' ? 'border-green-500 text-green-400' :
                                    selectedCall.summary.quality_grade === 'B' ? 'border-blue-500 text-blue-400' :
                                    selectedCall.summary.quality_grade === 'C' ? 'border-yellow-500 text-yellow-400' :
                                    'border-red-500 text-red-400'
                                  }`}>
                                    <span className="text-2xl font-bold">{selectedCall.summary.quality_grade}</span>
                                  </div>
                                  <div>
                                    <div className="text-2xl font-bold text-white">{selectedCall.summary.quality_score}/100</div>
                                    <div className="text-sm text-gray-400">Quality Score</div>
                                  </div>
                                </div>
                              )}
                              {/* Stats */}
                              <div className="grid grid-cols-3 gap-4 text-sm">
                                {selectedCall.summary.exchange_count !== undefined && (
                                  <div>
                                    <span className="text-gray-400 block">Exchanges</span>
                                    <span className="text-white">{selectedCall.summary.exchange_count}</span>
                                  </div>
                                )}
                                {selectedCall.summary.urgency_level && (
                                  <div>
                                    <span className="text-gray-400 block">Urgency</span>
                                    <span className="text-white capitalize">{selectedCall.summary.urgency_level}</span>
                                  </div>
                                )}
                                {selectedCall.summary.sentiment_score !== undefined && (
                                  <div>
                                    <span className="text-gray-400 block">Sentiment</span>
                                    <span className="text-white">{selectedCall.summary.sentiment_score > 0 ? '+' : ''}{selectedCall.summary.sentiment_score}</span>
                                  </div>
                                )}
                              </div>
                              {/* Quality Breakdown */}
                              {selectedCall.summary.quality_breakdown && (
                                <div className="space-y-2 pt-2 border-t border-zinc-700">
                                  <div className="text-sm text-gray-400 mb-2">Score Breakdown</div>
                                  {Object.entries(selectedCall.summary.quality_breakdown).map(([key, value]) => (
                                    <div key={key} className="flex items-center justify-between text-sm">
                                      <span className="text-gray-400 capitalize">{key.replace('_', ' ')}</span>
                                      <div className="flex items-center gap-2">
                                        <div className="w-20 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                                          <div className="h-full bg-amber-500 rounded-full" style={{ width: `${(value / 30) * 100}%` }} />
                                        </div>
                                        <span className="text-white w-6 text-right">{value}</span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="bg-zinc-800 rounded-lg p-4">
                          <p className="text-gray-500">No summary available for this call.</p>
                        </div>
                      )}

                      {/* Call Details */}
                      <div className="bg-zinc-800 rounded-lg p-4 space-y-3">
                        <h4 className="text-sm font-medium text-gray-400 mb-2">Call Details</h4>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-gray-400 block">Call Type</span>
                            <span className="text-white">{selectedCall.call_type}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 block">Minutes Used</span>
                            <span className="text-white">{selectedCall.minutes_used?.toFixed(2) || '0'}</span>
                          </div>
                          {selectedCall.phone_number && (
                            <div>
                              <span className="text-gray-400 block">Phone Number</span>
                              <span className="text-white">{selectedCall.phone_number}</span>
                            </div>
                          )}
                          {selectedCall.ended_reason && (
                            <div>
                              <span className="text-gray-400 block">End Reason</span>
                              <span className="text-white">{selectedCall.ended_reason}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Transcript Tab */}
                {activeTab === 'transcript' && (
                  <div className="max-w-3xl mx-auto">
                    {selectedCall.transcript && selectedCall.transcript.length > 0 ? (
                      <div className="space-y-4">
                        {selectedCall.transcript.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div className={`max-w-[80%] ${
                              msg.role === 'user'
                                ? 'bg-amber-500 text-black rounded-2xl rounded-br-sm'
                                : 'bg-zinc-800 text-white rounded-2xl rounded-bl-sm'
                            } px-4 py-3`}>
                              <div className={`text-xs mb-1 ${
                                msg.role === 'user' ? 'text-amber-900' : 'text-gray-400'
                              }`}>
                                {msg.role === 'user' ? 'Caller' : 'Assistant'}
                                {msg.timestamp && ` • ${msg.timestamp}`}
                              </div>
                              <p className="leading-relaxed">{msg.content}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-12 text-gray-500">
                        No transcript available for this call.
                      </div>
                    )}
                  </div>
                )}

                {/* Recording Tab */}
                {activeTab === 'recording' && (
                  <div className="max-w-2xl mx-auto">
                    {selectedCall.recording_url ? (
                      <div className="bg-zinc-800 rounded-xl p-6">
                        <div className="flex items-center justify-center mb-6">
                          <button
                            onClick={togglePlayback}
                            className="w-20 h-20 rounded-full bg-gold hover:bg-gold-shine flex items-center justify-center transition-colors"
                          >
                            {isPlaying ? (
                              <svg className="w-10 h-10 text-black" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                              </svg>
                            ) : (
                              <svg className="w-10 h-10 text-black ml-1" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M8 5v14l11-7z" />
                              </svg>
                            )}
                          </button>
                        </div>

                        {/* Progress Bar */}
                        <div className="space-y-2">
                          <input
                            type="range"
                            min="0"
                            max={audioDuration || 100}
                            value={audioProgress}
                            onChange={seekAudio}
                            className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer"
                            style={{
                              background: `linear-gradient(to right, #f59e0b ${(audioProgress / (audioDuration || 1)) * 100}%, #3f3f46 ${(audioProgress / (audioDuration || 1)) * 100}%)`
                            }}
                          />
                          <div className="flex justify-between text-sm text-gray-400">
                            <span>{formatDuration(audioProgress)}</span>
                            <span>{formatDuration(audioDuration || selectedCall.duration_seconds)}</span>
                          </div>
                        </div>

                        {/* Download Button */}
                        <div className="mt-6 text-center">
                          <a
                            href={selectedCall.recording_url}
                            download
                            className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Download Recording
                          </a>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-12">
                        <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-4">
                          <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                          </svg>
                        </div>
                        <p className="text-gray-400 mb-2">No recording available</p>
                        <p className="text-sm text-gray-500">
                          Enable call recording in Settings to record future calls.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Calls List */}
      {calls.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </div>
              <p className="text-gray-400">No calls yet</p>
              <p className="text-sm text-gray-500 mt-1">Start a conversation with an assistant to see your call history.</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-gray-400 border-b border-gold/10">
                    <th className="pb-3">Assistant</th>
                    <th className="pb-3">Date</th>
                    <th className="pb-3">Duration</th>
                    <th className="pb-3">Sentiment</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => (
                    <tr
                      key={call.id}
                      className="border-b border-gold/5 hover:bg-gold/5 transition-colors cursor-pointer"
                      onClick={() => loadCallDetail(call.id)}
                    >
                      <td className="py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center flex-shrink-0">
                            <span className="text-sm font-bold text-black">
                              {call.assistant_name.charAt(0)}
                            </span>
                          </div>
                          <div>
                            <div className="text-white font-medium">{call.assistant_name}</div>
                            <div className="text-xs text-gray-500">{call.call_type}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 text-sm text-gray-300">
                        {formatDate(call.started_at)}
                      </td>
                      <td className="py-4 text-sm text-white font-mono">
                        {formatDuration(call.duration_seconds)}
                      </td>
                      <td className="py-4">
                        {call.sentiment && (
                          <span className={`px-2 py-0.5 rounded text-xs ${getSentimentColor(call.sentiment)}`}>
                            {call.sentiment}
                          </span>
                        )}
                      </td>
                      <td className="py-4">
                        <span className={`px-2 py-0.5 rounded text-xs ${getStatusColor(call.status)}`}>
                          {call.status}
                        </span>
                      </td>
                      <td className="py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            loadCallDetail(call.id);
                          }}
                          className="text-gold text-sm hover:underline flex items-center gap-1"
                          disabled={loadingDetail}
                        >
                          View
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {total > limit && (
              <div className="flex justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="px-4 py-2 text-sm border border-gold/30 rounded-lg
                    text-gold hover:bg-gold/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <span className="px-4 py-2 text-sm text-gray-400">
                  Page {page + 1} of {Math.ceil(total / limit)}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={(page + 1) * limit >= total}
                  className="px-4 py-2 text-sm border border-gold/30 rounded-lg
                    text-gold hover:bg-gold/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
