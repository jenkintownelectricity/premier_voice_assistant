import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { colors, spacing } from '../lib/theme';
import { useAuth } from '../lib/auth-context';
import { api } from '../lib/api';

export function RedeemScreen() {
  const { user } = useAuth();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const handleRedeem = async () => {
    if (!code.trim() || !user?.id) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await api.redeemCode(user.id, code.trim());
      setResult({
        success: response.success,
        message: response.message,
      });
      if (response.success) {
        setCode('');
      }
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to redeem code',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <Text style={styles.title}>Redeem Code</Text>
      <Text style={styles.subtitle}>
        Enter your promotional code to claim bonus minutes
      </Text>

      <View style={[styles.card, styles.glowCard]}>
        <TextInput
          style={styles.input}
          placeholder="Enter code..."
          placeholderTextColor={colors.gray[500]}
          value={code}
          onChangeText={(text) => setCode(text.toUpperCase())}
          autoCapitalize="characters"
          autoCorrect={false}
        />

        <TouchableOpacity
          style={[styles.button, (!code.trim() || loading) && styles.buttonDisabled]}
          onPress={handleRedeem}
          disabled={!code.trim() || loading}
        >
          {loading ? (
            <ActivityIndicator color={colors.background} />
          ) : (
            <Text style={styles.buttonText}>Redeem Code</Text>
          )}
        </TouchableOpacity>

        {result && (
          <View style={[
            styles.resultContainer,
            result.success ? styles.successContainer : styles.errorContainer
          ]}>
            <Text style={result.success ? styles.successText : styles.errorText}>
              {result.success ? '✓ ' : '✗ '}{result.message}
            </Text>
          </View>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.gold,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 14,
    color: colors.gray[400],
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  card: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 16,
    padding: spacing.lg,
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
  input: {
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: spacing.md,
    fontSize: 20,
    color: colors.white,
    textAlign: 'center',
    letterSpacing: 4,
    fontFamily: 'monospace',
    borderWidth: 1,
    borderColor: colors.gray[700],
    marginBottom: spacing.md,
  },
  button: {
    backgroundColor: colors.gold,
    borderRadius: 12,
    padding: spacing.md,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
  resultContainer: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: 8,
  },
  successContainer: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  errorContainer: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  successText: {
    color: colors.success,
    fontSize: 14,
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
  },
});
