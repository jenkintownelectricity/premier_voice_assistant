import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  TextInput,
  Modal,
  Alert,
  Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing } from '../lib/theme';
import { useAuth } from '../lib/auth-context';
import { api, Assistant } from '../lib/api';

export function AssistantsScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [voiceId, setVoiceId] = useState('default');
  const [model, setModel] = useState('claude-sonnet-4-5-20250929');

  const fetchData = async () => {
    if (!user?.id) return;

    try {
      setError(null);
      const response = await api.getAssistants(user.id);
      setAssistants(response.assistants);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load assistants');
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

  const handleCreate = async () => {
    if (!user?.id || !name.trim() || !systemPrompt.trim()) {
      Alert.alert('Error', 'Please fill in name and system prompt');
      return;
    }

    setCreating(true);
    try {
      await api.createAssistant(user.id, {
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        description: description.trim() || undefined,
        voice_id: voiceId,
        model,
      });

      // Reset form
      setName('');
      setDescription('');
      setSystemPrompt('');
      setVoiceId('default');
      setModel('claude-sonnet-4-5-20250929');
      setShowCreate(false);

      // Reload list
      fetchData();
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to create assistant');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (assistant: Assistant) => {
    if (!user?.id) return;
    try {
      await api.updateAssistant(user.id, assistant.id, {
        is_active: !assistant.is_active,
      });
      fetchData();
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to update assistant');
    }
  };

  const handleDelete = async (assistant: Assistant) => {
    if (!user?.id) return;

    Alert.alert(
      'Delete Assistant',
      `Are you sure you want to delete "${assistant.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.deleteAssistant(user.id, assistant.id);
              fetchData();
            } catch (err) {
              Alert.alert('Error', err instanceof Error ? err.message : 'Failed to delete assistant');
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
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
        <View style={styles.header}>
          <Text style={styles.title}>AI Assistants</Text>
          <TouchableOpacity style={styles.createButton} onPress={() => setShowCreate(true)}>
            <Ionicons name="add" size={24} color={colors.background} />
          </TouchableOpacity>
        </View>

        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {assistants.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={48} color={colors.gray[600]} />
            <Text style={styles.emptyText}>No assistants yet</Text>
            <TouchableOpacity style={styles.emptyButton} onPress={() => setShowCreate(true)}>
              <Text style={styles.emptyButtonText}>Create Your First Assistant</Text>
            </TouchableOpacity>
          </View>
        ) : (
          assistants.map((assistant) => (
            <View key={assistant.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardTitleRow}>
                  <Text style={styles.cardTitle}>{assistant.name}</Text>
                  <View
                    style={[
                      styles.statusBadge,
                      { backgroundColor: assistant.is_active ? 'rgba(16, 185, 129, 0.2)' : 'rgba(115, 115, 115, 0.2)' },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusText,
                        { color: assistant.is_active ? colors.success : colors.gray[400] },
                      ]}
                    >
                      {assistant.is_active ? 'Active' : 'Inactive'}
                    </Text>
                  </View>
                </View>
                {assistant.description && (
                  <Text style={styles.cardDescription}>{assistant.description}</Text>
                )}
              </View>
              <View style={styles.cardMeta}>
                <Text style={styles.metaText}>Voice: {assistant.voice_id}</Text>
                <Text style={styles.metaText}>Calls: {assistant.call_count}</Text>
                <Text style={styles.metaText}>Created: {formatDate(assistant.created_at)}</Text>
              </View>
              <View style={styles.cardActions}>
                <TouchableOpacity
                  style={styles.actionButton}
                  onPress={() => handleToggleActive(assistant)}
                >
                  <Text style={styles.actionButtonText}>
                    {assistant.is_active ? 'Disable' : 'Enable'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.actionButton, styles.deleteButton]}
                  onPress={() => handleDelete(assistant)}
                >
                  <Text style={[styles.actionButtonText, styles.deleteButtonText]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Create Modal */}
      <Modal visible={showCreate} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreate(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Create Assistant</Text>
            <TouchableOpacity
              onPress={handleCreate}
              disabled={creating || !name.trim() || !systemPrompt.trim()}
            >
              <Text
                style={[
                  styles.modalSave,
                  { opacity: creating || !name.trim() || !systemPrompt.trim() ? 0.5 : 1 },
                ]}
              >
                {creating ? 'Creating...' : 'Create'}
              </Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent}>
            <Text style={styles.inputLabel}>Name *</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="My Assistant"
              placeholderTextColor={colors.gray[500]}
            />

            <Text style={styles.inputLabel}>Description</Text>
            <TextInput
              style={styles.input}
              value={description}
              onChangeText={setDescription}
              placeholder="What this assistant does..."
              placeholderTextColor={colors.gray[500]}
            />

            <Text style={styles.inputLabel}>System Prompt *</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              value={systemPrompt}
              onChangeText={setSystemPrompt}
              placeholder="You are a helpful AI assistant..."
              placeholderTextColor={colors.gray[500]}
              multiline
              numberOfLines={6}
              textAlignVertical="top"
            />

            <Text style={styles.inputLabel}>Voice</Text>
            <View style={styles.pickerContainer}>
              {['default', 'fabio', 'jake'].map((voice) => (
                <TouchableOpacity
                  key={voice}
                  style={[styles.pickerOption, voiceId === voice && styles.pickerOptionSelected]}
                  onPress={() => setVoiceId(voice)}
                >
                  <Text
                    style={[
                      styles.pickerOptionText,
                      voiceId === voice && styles.pickerOptionTextSelected,
                    ]}
                  >
                    {voice.charAt(0).toUpperCase() + voice.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.inputLabel}>Model</Text>
            <View style={styles.pickerContainer}>
              {[
                { id: 'claude-sonnet-4-5-20250929', name: 'Sonnet' },
                { id: 'claude-haiku-4-5-20241022', name: 'Haiku' },
              ].map((m) => (
                <TouchableOpacity
                  key={m.id}
                  style={[styles.pickerOption, model === m.id && styles.pickerOptionSelected]}
                  onPress={() => setModel(m.id)}
                >
                  <Text
                    style={[
                      styles.pickerOptionText,
                      model === m.id && styles.pickerOptionTextSelected,
                    ]}
                  >
                    {m.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.gold,
  },
  createButton: {
    backgroundColor: colors.gold,
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 12,
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
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
    marginBottom: spacing.lg,
  },
  emptyButton: {
    backgroundColor: colors.gold,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: 8,
  },
  emptyButtonText: {
    color: colors.background,
    fontWeight: '600',
  },
  card: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 16,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.gray[800],
  },
  cardHeader: {
    marginBottom: spacing.md,
  },
  cardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.white,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '500',
  },
  cardDescription: {
    fontSize: 14,
    color: colors.gray[400],
    marginTop: spacing.xs,
  },
  cardMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  metaText: {
    fontSize: 12,
    color: colors.gray[500],
  },
  cardActions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  actionButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.gold + '50',
  },
  actionButtonText: {
    color: colors.gold,
    fontSize: 14,
  },
  deleteButton: {
    borderColor: colors.error + '50',
  },
  deleteButtonText: {
    color: colors.error,
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
  modalCancel: {
    color: colors.gray[400],
    fontSize: 16,
  },
  modalTitle: {
    color: colors.gold,
    fontSize: 18,
    fontWeight: '600',
  },
  modalSave: {
    color: colors.gold,
    fontSize: 16,
    fontWeight: '600',
  },
  modalContent: {
    padding: spacing.md,
  },
  inputLabel: {
    color: colors.gold,
    fontSize: 14,
    fontWeight: '500',
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  input: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 8,
    padding: spacing.md,
    color: colors.white,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.gray[800],
  },
  textArea: {
    minHeight: 120,
  },
  pickerContainer: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  pickerOption: {
    flex: 1,
    padding: spacing.md,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.gray[800],
    alignItems: 'center',
  },
  pickerOptionSelected: {
    borderColor: colors.gold,
    backgroundColor: colors.gold + '20',
  },
  pickerOptionText: {
    color: colors.gray[400],
    fontSize: 14,
  },
  pickerOptionTextSelected: {
    color: colors.gold,
    fontWeight: '600',
  },
});
