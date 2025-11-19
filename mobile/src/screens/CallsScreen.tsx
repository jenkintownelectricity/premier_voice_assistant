import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing } from '../lib/theme';
import { useAuth } from '../lib/auth-context';
import { api, CallLog, CallDetail, CallStats } from '../lib/api';

export function CallsScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [stats, setStats] = useState<CallStats | null>(null);
  const [selectedCall, setSelectedCall] = useState<CallDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  const fetchData = async (reset = false) => {
    if (!user?.id) return;

    try {
      setError(null);
      const newOffset = reset ? 0 : offset;

      const [callsRes, statsRes] = await Promise.all([
        api.getCalls(user.id, limit, newOffset),
        api.getCallStats(user.id),
      ]);

      if (reset) {
        setCalls(callsRes.calls);
        setOffset(0);
      } else {
        setCalls(callsRes.calls);
      }
      setTotal(callsRes.total);
      setStats(statsRes.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calls');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData(true);
  }, [user?.id]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData(true);
  };

  const loadMore = async () => {
    if (!user?.id || calls.length >= total) return;

    const newOffset = offset + limit;
    try {
      const response = await api.getCalls(user.id, limit, newOffset);
      setCalls([...calls, ...response.calls]);
      setOffset(newOffset);
    } catch (err) {
      console.error('Failed to load more calls:', err);
    }
  };

  const viewCallDetail = async (callId: string) => {
    if (!user?.id) return;

    setLoadingDetail(true);
    try {
      const response = await api.getCall(user.id, callId);
      setSelectedCall(response.call);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load call details');
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatCost = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return colors.success;
      case 'failed':
        return colors.error;
      case 'in_progress':
        return colors.warning;
      default:
        return colors.gray[400];
    }
  };

  const getSentimentColor = (sentiment: string | null) => {
    switch (sentiment) {
      case 'positive':
        return colors.success;
      case 'negative':
        return colors.error;
      default:
        return colors.gray[400];
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.gold} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />
        }
      >
        <Text style={styles.title}>Call Logs</Text>

        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* Stats Grid */}
        {stats && (
          <View style={styles.statsGrid}>
            <View style={styles.statCard}>
              <Text style={styles.statNumber}>{stats.total_calls}</Text>
              <Text style={styles.statLabel}>Total Calls</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statNumber}>{formatDuration(stats.total_duration_seconds)}</Text>
              <Text style={styles.statLabel}>Total Duration</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statNumber}>{formatCost(stats.total_cost_cents)}</Text>
              <Text style={styles.statLabel}>Total Cost</Text>
            </View>
            <View style={styles.statCard}>
              <Text style={styles.statNumber}>{stats.calls_today}</Text>
              <Text style={styles.statLabel}>Today</Text>
            </View>
          </View>
        )}

        {/* Calls List */}
        {calls.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="call-outline" size={48} color={colors.gray[600]} />
            <Text style={styles.emptyText}>No calls yet</Text>
          </View>
        ) : (
          <>
            {calls.map((call) => (
              <TouchableOpacity
                key={call.id}
                style={styles.card}
                onPress={() => viewCallDetail(call.id)}
              >
                <View style={styles.cardHeader}>
                  <Text style={styles.cardTitle}>{call.assistant_name}</Text>
                  <View
                    style={[
                      styles.statusBadge,
                      { backgroundColor: getStatusColor(call.status) + '20' },
                    ]}
                  >
                    <Text style={[styles.statusText, { color: getStatusColor(call.status) }]}>
                      {call.status}
                    </Text>
                  </View>
                </View>
                <View style={styles.cardMeta}>
                  <Text style={styles.metaText}>{formatDate(call.started_at)}</Text>
                  <Text style={styles.metaText}>{formatDuration(call.duration_seconds)}</Text>
                  <Text style={styles.metaText}>{formatCost(call.cost_cents)}</Text>
                </View>
                {call.summary && (
                  <Text style={styles.cardSummary} numberOfLines={2}>
                    {call.summary}
                  </Text>
                )}
                {call.sentiment && (
                  <View style={styles.sentimentRow}>
                    <Ionicons
                      name={
                        call.sentiment === 'positive'
                          ? 'happy-outline'
                          : call.sentiment === 'negative'
                          ? 'sad-outline'
                          : 'remove-outline'
                      }
                      size={16}
                      color={getSentimentColor(call.sentiment)}
                    />
                    <Text style={[styles.sentimentText, { color: getSentimentColor(call.sentiment) }]}>
                      {call.sentiment}
                    </Text>
                  </View>
                )}
              </TouchableOpacity>
            ))}

            {calls.length < total && (
              <TouchableOpacity style={styles.loadMoreButton} onPress={loadMore}>
                <Text style={styles.loadMoreText}>Load More</Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </ScrollView>

      {/* Call Detail Modal */}
      <Modal
        visible={selectedCall !== null}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setSelectedCall(null)}>
              <Ionicons name="close" size={24} color={colors.gray[400]} />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Call Details</Text>
            <View style={{ width: 24 }} />
          </View>

          {loadingDetail ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={colors.gold} />
            </View>
          ) : selectedCall ? (
            <ScrollView style={styles.modalContent}>
              {/* Call Info */}
              <View style={styles.detailSection}>
                <Text style={styles.detailLabel}>Assistant</Text>
                <Text style={styles.detailValue}>{selectedCall.assistant_name}</Text>
              </View>

              <View style={styles.detailRow}>
                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Duration</Text>
                  <Text style={styles.detailValue}>
                    {formatDuration(selectedCall.duration_seconds)}
                  </Text>
                </View>
                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Cost</Text>
                  <Text style={styles.detailValue}>{formatCost(selectedCall.cost_cents)}</Text>
                </View>
              </View>

              <View style={styles.detailRow}>
                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Status</Text>
                  <Text style={[styles.detailValue, { color: getStatusColor(selectedCall.status) }]}>
                    {selectedCall.status}
                  </Text>
                </View>
                {selectedCall.sentiment && (
                  <View style={styles.detailSection}>
                    <Text style={styles.detailLabel}>Sentiment</Text>
                    <Text
                      style={[
                        styles.detailValue,
                        { color: getSentimentColor(selectedCall.sentiment) },
                      ]}
                    >
                      {selectedCall.sentiment}
                    </Text>
                  </View>
                )}
              </View>

              <View style={styles.detailSection}>
                <Text style={styles.detailLabel}>Started</Text>
                <Text style={styles.detailValue}>{formatDate(selectedCall.started_at)}</Text>
              </View>

              {selectedCall.summary && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailLabel}>Summary</Text>
                  <Text style={styles.detailValue}>{selectedCall.summary}</Text>
                </View>
              )}

              {/* Transcript */}
              {selectedCall.transcript && selectedCall.transcript.length > 0 && (
                <View style={styles.transcriptSection}>
                  <Text style={styles.transcriptTitle}>Transcript</Text>
                  {selectedCall.transcript.map((msg, index) => (
                    <View
                      key={index}
                      style={[
                        styles.transcriptMessage,
                        msg.role === 'assistant'
                          ? styles.transcriptAssistant
                          : styles.transcriptUser,
                      ]}
                    >
                      <Text style={styles.transcriptRole}>
                        {msg.role === 'assistant' ? 'Assistant' : 'User'}
                      </Text>
                      <Text style={styles.transcriptContent}>{msg.content}</Text>
                    </View>
                  ))}
                </View>
              )}
            </ScrollView>
          ) : null}
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.gold,
    marginBottom: spacing.lg,
  },
  errorContainer: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    padding: spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.gray[800],
  },
  statNumber: {
    fontSize: 20,
    fontWeight: 'bold',
    color: colors.gold,
  },
  statLabel: {
    fontSize: 11,
    color: colors.gray[400],
    marginTop: spacing.xs,
  },
  emptyContainer: {
    alignItems: 'center',
    padding: spacing.xl,
    marginTop: spacing.xl,
  },
  emptyText: {
    color: colors.gray[400],
    fontSize: 16,
    marginTop: spacing.md,
  },
  card: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    marginBottom: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.gray[800],
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.white,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '500',
  },
  cardMeta: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  metaText: {
    fontSize: 12,
    color: colors.gray[500],
  },
  cardSummary: {
    fontSize: 13,
    color: colors.gray[400],
    marginBottom: spacing.sm,
  },
  sentimentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  sentimentText: {
    fontSize: 12,
    textTransform: 'capitalize',
  },
  loadMoreButton: {
    alignItems: 'center',
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  loadMoreText: {
    color: colors.gold,
    fontSize: 14,
    fontWeight: '500',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[800],
  },
  modalTitle: {
    color: colors.gold,
    fontSize: 18,
    fontWeight: '600',
  },
  modalContent: {
    padding: spacing.md,
  },
  detailSection: {
    marginBottom: spacing.lg,
  },
  detailRow: {
    flexDirection: 'row',
    gap: spacing.lg,
  },
  detailLabel: {
    fontSize: 12,
    color: colors.gray[500],
    marginBottom: spacing.xs,
  },
  detailValue: {
    fontSize: 16,
    color: colors.white,
  },
  transcriptSection: {
    marginTop: spacing.md,
  },
  transcriptTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.gold,
    marginBottom: spacing.md,
  },
  transcriptMessage: {
    padding: spacing.md,
    borderRadius: 12,
    marginBottom: spacing.sm,
    maxWidth: '85%',
  },
  transcriptAssistant: {
    backgroundColor: colors.surfaceLight,
    alignSelf: 'flex-start',
  },
  transcriptUser: {
    backgroundColor: colors.gold + '20',
    alignSelf: 'flex-end',
  },
  transcriptRole: {
    fontSize: 11,
    color: colors.gray[500],
    marginBottom: spacing.xs,
    fontWeight: '500',
  },
  transcriptContent: {
    fontSize: 14,
    color: colors.white,
    lineHeight: 20,
  },
});
