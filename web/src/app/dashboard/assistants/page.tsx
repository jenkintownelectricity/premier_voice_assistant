'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input } from '@/components/Input';
import { VoiceCall } from '@/components/VoiceCall';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface Assistant {
  id: string;
  name: string;
  description: string | null;
  voice_id: string;
  model: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  call_count: number;
}

// Industry-specific quick start templates
const ASSISTANT_TEMPLATES = [
  {
    id: 'custom',
    name: 'Custom',
    icon: '✨',
    description: 'Start from scratch',
    system_prompt: '',
    first_message: '',
  },
  {
    id: 'plumber',
    name: 'Plumber / HVAC',
    icon: '🔧',
    description: 'Emergency repairs, scheduling, quotes',
    system_prompt: `You are a friendly and professional phone assistant for a plumbing/HVAC company. Your role is to:

1. Greet callers warmly and get their name
2. Identify if it's an EMERGENCY (water leak, no heat, gas smell) - if so, assure them help is on the way
3. For non-emergencies: capture their service need, address, and preferred callback time
4. Mention we offer free estimates for major work
5. Always be empathetic - plumbing problems are stressful!

Keep responses SHORT (1-2 sentences) since this is voice. Be warm but efficient.`,
    first_message: "Hi there! Thanks for calling. Are you dealing with an emergency, or looking to schedule a service appointment?",
  },
  {
    id: 'electrician',
    name: 'Electrician',
    icon: '⚡',
    description: 'Electrical services, safety, scheduling',
    system_prompt: `You are a professional phone assistant for an electrical contractor. Your role is to:

1. Greet callers and identify if this is an EMERGENCY (sparks, burning smell, power out to whole house)
2. For emergencies: Get their address immediately and assure 24/7 emergency service
3. For regular calls: Understand their electrical need (panel upgrade, outlet install, troubleshooting)
4. Capture their contact info and preferred appointment time
5. Mention we're licensed, bonded, and insured

SAFETY FIRST - if they describe anything dangerous, advise them to stay away from the area.
Keep responses brief and professional.`,
    first_message: "Hello! Thanks for calling. Is this an electrical emergency, or are you looking to schedule service?",
  },
  {
    id: 'law_office',
    name: 'Law Office',
    icon: '⚖️',
    description: 'Legal intake, consultations, scheduling',
    system_prompt: `You are a professional receptionist for a law firm. Your role is to:

1. Greet callers professionally and identify their legal matter type
2. Gather basic information: name, contact, brief description of their situation
3. Explain that an attorney will review their case and call back
4. For urgent matters: Note the urgency for priority callback
5. Be warm but maintain professional boundaries - never give legal advice

IMPORTANT:
- Never provide legal advice or opinions
- Keep information confidential
- Note any statute of limitations concerns they mention

Keep responses professional and concise.`,
    first_message: "Good day, thank you for calling our law office. How may I assist you today?",
  },
  {
    id: 'medical_office',
    name: 'Medical Office',
    icon: '🏥',
    description: 'Appointments, prescription refills, triage',
    system_prompt: `You are a compassionate medical office assistant. Your role is to:

1. Greet patients warmly
2. Identify the reason for call: appointment scheduling, prescription refill, medical question
3. For appointments: Check patient name, preferred date/time, reason for visit
4. For prescriptions: Get medication name and pharmacy preference
5. For urgent symptoms: Advise calling 911 or going to ER if life-threatening

IMPORTANT:
- Never diagnose or provide medical advice
- For emergencies, always direct to 911
- Maintain HIPAA awareness in your responses

Keep responses warm and efficient.`,
    first_message: "Hello! Thank you for calling. Are you calling to schedule an appointment, refill a prescription, or something else?",
  },
  {
    id: 'restaurant',
    name: 'Restaurant',
    icon: '🍽️',
    description: 'Reservations, hours, takeout orders',
    system_prompt: `You are a friendly host/hostess for a restaurant. Your role is to:

1. Greet callers with warmth and energy
2. Handle reservation requests: Get party size, date, time, name, and contact
3. Answer common questions: hours, location, parking, menu highlights
4. For takeout: Direct them to our online ordering or take their order
5. Mention any current specials or events

Be friendly, upbeat, and make them excited to dine with us!
Keep responses brief but welcoming.`,
    first_message: "Hey there! Thanks for calling! Are you looking to make a reservation, place a takeout order, or do you have a question?",
  },
  {
    id: 'real_estate',
    name: 'Real Estate',
    icon: '🏠',
    description: 'Property inquiries, showings, listings',
    system_prompt: `You are a professional assistant for a real estate agent/team. Your role is to:

1. Greet callers and identify if they're buying, selling, or renting
2. For buyers: Get their criteria (location, bedrooms, budget, timeline)
3. For sellers: Understand their property and timeline
4. Capture contact info for agent follow-up
5. Schedule showings or consultations when requested

Be enthusiastic about helping them with their real estate journey!
Keep responses professional yet personable.`,
    first_message: "Hi! Thanks for calling! Are you looking to buy, sell, or rent a property?",
  },
  {
    id: 'auto_shop',
    name: 'Auto Repair',
    icon: '🚗',
    description: 'Service appointments, diagnostics, quotes',
    system_prompt: `You are a helpful assistant for an auto repair shop. Your role is to:

1. Greet callers and identify their vehicle issue
2. Ask about vehicle make, model, year
3. Determine if car is drivable or needs towing
4. Schedule service appointments
5. Provide rough estimates when possible, noting final price depends on diagnosis

Be friendly and reassuring - car trouble is stressful!
Keep responses helpful but brief.`,
    first_message: "Hi there! Thanks for calling. What's going on with your vehicle today?",
  },
  {
    id: 'general_business',
    name: 'General Business',
    icon: '💼',
    description: 'Professional call handling for any business',
    system_prompt: `You are a professional virtual receptionist. Your role is to:

1. Greet callers warmly and professionally
2. Identify the purpose of their call
3. Capture their name, contact information, and message
4. Note any urgency or time-sensitive matters
5. Assure them their message will be delivered promptly

Be professional, efficient, and courteous.
Keep responses clear and concise.`,
    first_message: "Hello! Thank you for calling. How may I direct your call today?",
  },
];

export default function AssistantsPage() {
  const { user } = useAuth();
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeCall, setActiveCall] = useState<{ id: string; name: string } | null>(null);

  // Template selection
  const [selectedTemplate, setSelectedTemplate] = useState('custom');

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [voiceId, setVoiceId] = useState('default');
  const [model, setModel] = useState('claude-sonnet-4-5-20250929');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(150);
  const [firstMessage, setFirstMessage] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Advanced latency settings
  const [vadSensitivity, setVadSensitivity] = useState(0.5);
  const [endpointingMs, setEndpointingMs] = useState(600);
  const [enableBargein, setEnableBargein] = useState(true);
  const [streamingChunks, setStreamingChunks] = useState(true);
  const [firstMessageLatencyMs, setFirstMessageLatencyMs] = useState(800);
  const [turnDetectionMode, setTurnDetectionMode] = useState('server_vad');

  useEffect(() => {
    if (user?.id) {
      loadAssistants();
    }
  }, [user?.id]);

  // Handle template selection
  const handleTemplateSelect = (templateId: string) => {
    setSelectedTemplate(templateId);
    const template = ASSISTANT_TEMPLATES.find(t => t.id === templateId);
    if (template) {
      setSystemPrompt(template.system_prompt);
      setFirstMessage(template.first_message);
      if (templateId !== 'custom') {
        setName(template.name + ' Assistant');
        setDescription(template.description);
      }
    }
  };

  const loadAssistants = async () => {
    if (!user?.id) return;
    try {
      const response = await api.getAssistants(user.id);
      setAssistants(response.assistants);
    } catch (err) {
      console.error('Failed to load assistants:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!user?.id || !name.trim() || !systemPrompt.trim()) return;

    setCreating(true);
    try {
      await api.createAssistant(user.id, {
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        description: description.trim() || undefined,
        voice_id: voiceId,
        model,
        temperature,
        max_tokens: maxTokens,
        first_message: firstMessage.trim() || undefined,
        vad_sensitivity: vadSensitivity,
        endpointing_ms: endpointingMs,
        enable_bargein: enableBargein,
        streaming_chunks: streamingChunks,
        first_message_latency_ms: firstMessageLatencyMs,
        turn_detection_mode: turnDetectionMode,
      });

      // Reset form
      setName('');
      setDescription('');
      setSystemPrompt('');
      setVoiceId('default');
      setModel('claude-sonnet-4-5-20250929');
      setTemperature(0.7);
      setMaxTokens(150);
      setFirstMessage('');
      setShowAdvanced(false);
      setVadSensitivity(0.5);
      setEndpointingMs(600);
      setEnableBargein(true);
      setStreamingChunks(true);
      setFirstMessageLatencyMs(800);
      setTurnDetectionMode('server_vad');
      setSelectedTemplate('custom');
      setShowCreate(false);

      // Reload list
      loadAssistants();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create assistant');
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
      loadAssistants();
    } catch (err) {
      console.error('Failed to update assistant:', err);
    }
  };

  const handleDelete = async (assistantId: string) => {
    if (!user?.id) return;
    if (!confirm('Are you sure you want to delete this assistant?')) return;

    try {
      await api.deleteAssistant(user.id, assistantId);
      loadAssistants();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete assistant');
    }
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
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading assistants...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">AI Assistants</h1>
          <p className="text-gray-400 mt-1">
            Create and manage your voice AI agents
          </p>
        </div>
        <HoneycombButton onClick={() => setShowCreate(true)}>
          + Create Assistant
        </HoneycombButton>
      </div>

      {/* Create Form */}
      {showCreate && (
        <Card glow>
          <CardTitle>Create New Assistant</CardTitle>
          <CardContent>
            <div className="space-y-4">
              {/* Quick Start Templates */}
              <div>
                <label className="block text-sm font-medium text-gold mb-3">
                  Quick Start Template
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                  {ASSISTANT_TEMPLATES.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      onClick={() => handleTemplateSelect(template.id)}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedTemplate === template.id
                          ? 'border-gold bg-gold/10 text-gold'
                          : 'border-gray-700 bg-oled-dark text-gray-300 hover:border-gold/50'
                      }`}
                    >
                      <div className="text-2xl mb-1">{template.icon}</div>
                      <div className="text-sm font-medium truncate">{template.name}</div>
                      <div className="text-xs text-gray-500 truncate">{template.description}</div>
                    </button>
                  ))}
                </div>
                {selectedTemplate !== 'custom' && (
                  <p className="text-xs text-green-400 mt-2">
                    Template applied! Customize the settings below as needed.
                  </p>
                )}
              </div>

              <div className="border-t border-gold/10 pt-4" />

              <Input
                label="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Assistant"
              />
              <Input
                label="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this assistant does..."
              />
              <div>
                <label className="block text-sm font-medium text-gold mb-2">
                  System Prompt
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="You are a helpful AI assistant..."
                  className="w-full px-4 py-3 bg-oled-dark border border-gold/30 rounded-lg
                    text-white placeholder-gray-500 focus:outline-none focus:border-gold
                    transition-colors min-h-[120px]"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gold mb-2">
                    Voice
                  </label>
                  <select
                    value={voiceId}
                    onChange={(e) => setVoiceId(e.target.value)}
                    className="w-full px-4 py-3 bg-oled-dark border border-gold/30 rounded-lg
                      text-white focus:outline-none focus:border-gold transition-colors"
                  >
                    <option value="default">Default</option>
                    <option value="fabio">Fabio</option>
                    <option value="jake">Jake</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gold mb-2">
                    Model
                  </label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full px-4 py-3 bg-oled-dark border border-gold/30 rounded-lg
                      text-white focus:outline-none focus:border-gold transition-colors"
                  >
                    <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
                    <option value="claude-haiku-3-5-20241022">Claude Haiku 3.5</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gold mb-2">
                  First Message (optional)
                </label>
                <Input
                  value={firstMessage}
                  onChange={(e) => setFirstMessage(e.target.value)}
                  placeholder="Hello! How can I help you today?"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Initial greeting when a call starts
                </p>
              </div>

              {/* Advanced Settings Toggle */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-sm text-gold hover:text-gold/80 transition-colors"
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Advanced Settings (Latency Optimization)
              </button>

              {/* Advanced Settings Section */}
              {showAdvanced && (
                <div className="space-y-4 p-4 bg-oled-dark/50 rounded-lg border border-gold/10">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gold mb-2">
                        Temperature ({temperature})
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={temperature}
                        onChange={(e) => setTemperature(parseFloat(e.target.value))}
                        className="w-full accent-gold"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Lower = more focused, Higher = more creative
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gold mb-2">
                        Max Tokens
                      </label>
                      <input
                        type="number"
                        min="50"
                        max="500"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                        className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                          text-white focus:outline-none focus:border-gold transition-colors"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Max response length (50-500)
                      </p>
                    </div>
                  </div>

                  <div className="border-t border-gold/10 pt-4">
                    <h4 className="text-sm font-medium text-gold mb-3">Latency Optimization</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          VAD Sensitivity ({vadSensitivity})
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={vadSensitivity}
                          onChange={(e) => setVadSensitivity(parseFloat(e.target.value))}
                          className="w-full accent-gold"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Voice Activity Detection threshold
                        </p>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Endpointing Delay (ms)
                        </label>
                        <input
                          type="number"
                          min="200"
                          max="2000"
                          step="100"
                          value={endpointingMs}
                          onChange={(e) => setEndpointingMs(parseInt(e.target.value))}
                          className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                            text-white focus:outline-none focus:border-gold transition-colors"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Silence duration to detect end of speech
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        First Message Latency (ms)
                      </label>
                      <input
                        type="number"
                        min="300"
                        max="2000"
                        step="100"
                        value={firstMessageLatencyMs}
                        onChange={(e) => setFirstMessageLatencyMs(parseInt(e.target.value))}
                        className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                          text-white focus:outline-none focus:border-gold transition-colors"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Target latency for initial response
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Turn Detection Mode
                      </label>
                      <select
                        value={turnDetectionMode}
                        onChange={(e) => setTurnDetectionMode(e.target.value)}
                        className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                          text-white focus:outline-none focus:border-gold transition-colors"
                      >
                        <option value="server_vad">Server VAD</option>
                        <option value="semantic">Semantic</option>
                        <option value="both">Both</option>
                      </select>
                      <p className="text-xs text-gray-500 mt-1">
                        How to detect when user finishes speaking
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 pt-2">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enableBargein}
                        onChange={(e) => setEnableBargein(e.target.checked)}
                        className="w-4 h-4 rounded border-gold/30 bg-oled-dark text-gold
                          focus:ring-gold focus:ring-offset-0"
                      />
                      <div>
                        <span className="text-sm text-gray-300">Enable Barge-in</span>
                        <p className="text-xs text-gray-500">
                          Allow user to interrupt assistant
                        </p>
                      </div>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={streamingChunks}
                        onChange={(e) => setStreamingChunks(e.target.checked)}
                        className="w-4 h-4 rounded border-gold/30 bg-oled-dark text-gold
                          focus:ring-gold focus:ring-offset-0"
                      />
                      <div>
                        <span className="text-sm text-gray-300">Streaming Chunks</span>
                        <p className="text-xs text-gray-500">
                          Stream TTS output for faster response
                        </p>
                      </div>
                    </label>
                  </div>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <HoneycombButton
                  onClick={handleCreate}
                  disabled={creating || !name.trim() || !systemPrompt.trim()}
                >
                  {creating ? 'Creating...' : 'Create Assistant'}
                </HoneycombButton>
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Assistants List */}
      {assistants.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-8">
              <div className="text-gray-400 mb-4">No assistants yet</div>
              <HoneycombButton onClick={() => setShowCreate(true)}>
                Create Your First Assistant
              </HoneycombButton>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {assistants.map((assistant) => (
            <Card key={assistant.id}>
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-white">
                        {assistant.name}
                      </h3>
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          assistant.is_active
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {assistant.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    {assistant.description && (
                      <p className="text-gray-400 text-sm mt-1">
                        {assistant.description}
                      </p>
                    )}
                    <div className="flex gap-4 mt-3 text-sm text-gray-500">
                      <span>Voice: {assistant.voice_id}</span>
                      <span>Calls: {assistant.call_count}</span>
                      <span>Created: {formatDate(assistant.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {assistant.is_active && (
                      <button
                        onClick={() => setActiveCall({ id: assistant.id, name: assistant.name })}
                        className="px-3 py-1.5 text-sm bg-gold text-black rounded
                          hover:bg-gold/80 transition-colors font-medium"
                      >
                        Start Call
                      </button>
                    )}
                    <button
                      onClick={() => handleToggleActive(assistant)}
                      className="px-3 py-1.5 text-sm border border-gold/30 rounded
                        text-gold hover:bg-gold/10 transition-colors"
                    >
                      {assistant.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={() => handleDelete(assistant.id)}
                      className="px-3 py-1.5 text-sm border border-red-500/30 rounded
                        text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Voice Call - Full Screen */}
      {activeCall && user && (
        <div className="fixed inset-0 z-50">
          <VoiceCall
            assistantId={activeCall.id}
            assistantName={activeCall.name}
            userId={user.id}
            onClose={() => {
              setActiveCall(null);
              loadAssistants(); // Refresh to update call count
            }}
          />
        </div>
      )}
    </div>
  );
}
