import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Image,
} from 'react-native';
import { colors, spacing } from '../lib/theme';
import { useAuth } from '../lib/auth-context';
import { api, Usage, FeatureLimits } from '../lib/api';

export function DashboardScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [limits, setLimits] = useState<FeatureLimits | null>(null);

  const fetchData = async () => {
    if (!user?.id) return;

    try {
      setError(null);
      const [usageRes, limitsRes] = await Promise.all([
        api.getUsage(user.id),
        api.getFeatureLimits(user.id),
      ]);
      setUsage(usageRes.usage);
      setLimits(limitsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [user?.id]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.gold} />
      </View>
    );
  }

  const totalMinutes = (limits?.limits.max_minutes || 100) + (usage?.bonus_minutes || 0);
  const usedMinutes = usage?.minutes_used || 0;
  const usagePercent = totalMinutes > 0 ? (usedMinutes / totalMinutes) * 100 : 0;
  const progressWidth = Math.min(usagePercent, 100);

  return (
    <View style={styles.wrapper}>
      {/* Background logo watermark */}
      <Image
        source={require('../../assets/HIVE215Logo.png')}
        style={styles.watermark}
        resizeMode="contain"
      />
      <ScrollView
        style={styles.container}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.gold} />
        }
      >
        <Text style={styles.title}>Dashboard</Text>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Current Plan</Text>
        <Text style={styles.planName}>{limits?.display_name || 'Free'}</Text>
      </View>

      <View style={[styles.card, styles.glowCard]}>
        <Text style={styles.cardLabel}>Minutes Used</Text>
        <View style={styles.usageRow}>
          <Text style={styles.usageNumber}>{usedMinutes.toLocaleString()}</Text>
          <Text style={styles.usageTotal}>/ {totalMinutes.toLocaleString()}</Text>
        </View>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${progressWidth}%` }]} />
        </View>
        {(usage?.bonus_minutes || 0) > 0 && (
          <Text style={styles.bonusText}>+{usage?.bonus_minutes} bonus minutes</Text>
        )}
      </View>

      <View style={styles.statsGrid}>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{usage?.conversations_count || 0}</Text>
          <Text style={styles.statLabel}>Conversations</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{usage?.voice_clones_count || 0}</Text>
          <Text style={styles.statLabel}>Voice Clones</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{usage?.assistants_count || 0}</Text>
          <Text style={styles.statLabel}>Assistants</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{totalMinutes - usedMinutes}</Text>
          <Text style={styles.statLabel}>Remaining</Text>
        </View>
      </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    flex: 1,
    backgroundColor: colors.background,
  },
  watermark: {
    position: 'absolute',
    width: 300,
    height: 300,
    alignSelf: 'center',
    top: '30%',
    opacity: 0.03,
  },
  container: {
    flex: 1,
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
  card: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.gray[800],
  },
  glowCard: {
    borderColor: colors.gold,
    shadowColor: colors.gold,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 10,
  },
  cardLabel: {
    fontSize: 14,
    color: colors.gray[400],
    marginBottom: spacing.xs,
  },
  planName: {
    fontSize: 28,
    fontWeight: 'bold',
    color: colors.gold,
  },
  usageRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  usageNumber: {
    fontSize: 36,
    fontWeight: 'bold',
    color: colors.gold,
  },
  usageTotal: {
    fontSize: 18,
    color: colors.gray[400],
    marginLeft: spacing.xs,
  },
  progressBar: {
    height: 8,
    backgroundColor: colors.gray[700],
    borderRadius: 4,
    marginTop: spacing.md,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.gold,
    borderRadius: 4,
  },
  bonusText: {
    fontSize: 12,
    color: colors.success,
    marginTop: spacing.sm,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
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
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.gold,
  },
  statLabel: {
    fontSize: 12,
    color: colors.gray[400],
    marginTop: spacing.xs,
  },
});
