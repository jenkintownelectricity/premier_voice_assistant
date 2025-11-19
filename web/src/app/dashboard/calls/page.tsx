'use client';

import { useState, useEffect } from 'react';
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
  transcript: Array<{ role: string; content: string; timestamp?: string }>;
  summary: string | null;
  recording_url: string | null;
  sentiment: string | null;
  ended_reason: string | null;
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
  const limit = 20;

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
    try {
      const response = await api.getCall(user.id, callId);
      setSelectedCall(response.call);
    } catch (err) {
      console.error('Failed to load call detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-400 bg-green-500/20';
      case 'failed':
        return 'text-red-400 bg-red-500/20';
      case 'in_progress':
        return 'text-yellow-400 bg-yellow-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getSentimentColor = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive':
        return 'text-green-400';
      case 'negative':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
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
      <div>
        <h1 className="text-3xl font-bold text-gold">Call Logs</h1>
        <p className="text-gray-400 mt-1">
          View your conversation history and analytics
        </p>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
              <div className="text-2xl font-bold text-gold">{stats.calls_today}</div>
              <div className="text-sm text-gray-400">Today</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Call Detail Modal */}
      {selectedCall && (
        <Card glow>
          <CardTitle>
            <div className="flex justify-between items-center">
              <span>Call Details</span>
              <button
                onClick={() => setSelectedCall(null)}
                className="text-gray-400 hover:text-white"
              >
                Close
              </button>
            </div>
          </CardTitle>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Assistant:</span>
                  <span className="ml-2 text-white">{selectedCall.assistant_name}</span>
                </div>
                <div>
                  <span className="text-gray-400">Duration:</span>
                  <span className="ml-2 text-white">
                    {formatDuration(selectedCall.duration_seconds)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Cost:</span>
                  <span className="ml-2 text-white">
                    {formatCost(selectedCall.cost_cents)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Status:</span>
                  <span className={`ml-2 ${getSentimentColor(selectedCall.sentiment)}`}>
                    {selectedCall.status}
                  </span>
                </div>
              </div>

              {selectedCall.summary && (
                <div>
                  <div className="text-sm text-gray-400 mb-1">Summary</div>
                  <div className="text-white text-sm bg-oled-dark p-3 rounded">
                    {selectedCall.summary}
                  </div>
                </div>
              )}

              {selectedCall.transcript && selectedCall.transcript.length > 0 && (
                <div>
                  <div className="text-sm text-gray-400 mb-2">Transcript</div>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {selectedCall.transcript.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`p-2 rounded text-sm ${
                          msg.role === 'user'
                            ? 'bg-gold/10 text-gold ml-4'
                            : 'bg-gray-800 text-white mr-4'
                        }`}
                      >
                        <div className="text-xs text-gray-500 mb-1">
                          {msg.role === 'user' ? 'User' : 'Assistant'}
                        </div>
                        {msg.content}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Calls List */}
      {calls.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-8 text-gray-400">
              No calls yet. Start a conversation with an assistant to see your call history.
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
                    <th className="pb-3">Cost</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => (
                    <tr
                      key={call.id}
                      className="border-b border-gold/5 hover:bg-gold/5 transition-colors"
                    >
                      <td className="py-3">
                        <div className="text-white">{call.assistant_name}</div>
                        <div className="text-xs text-gray-500">{call.call_type}</div>
                      </td>
                      <td className="py-3 text-sm text-gray-300">
                        {formatDate(call.started_at)}
                      </td>
                      <td className="py-3 text-sm text-white">
                        {formatDuration(call.duration_seconds)}
                      </td>
                      <td className="py-3 text-sm text-white">
                        {formatCost(call.cost_cents)}
                      </td>
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${getStatusColor(
                            call.status
                          )}`}
                        >
                          {call.status}
                        </span>
                      </td>
                      <td className="py-3">
                        <button
                          onClick={() => loadCallDetail(call.id)}
                          className="text-gold text-sm hover:underline"
                          disabled={loadingDetail}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {total > limit && (
              <div className="flex justify-center gap-2 mt-4">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="px-3 py-1 text-sm border border-gold/30 rounded
                    text-gold hover:bg-gold/10 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="px-3 py-1 text-sm text-gray-400">
                  Page {page + 1} of {Math.ceil(total / limit)}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={(page + 1) * limit >= total}
                  className="px-3 py-1 text-sm border border-gold/30 rounded
                    text-gold hover:bg-gold/10 disabled:opacity-50 disabled:cursor-not-allowed"
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
