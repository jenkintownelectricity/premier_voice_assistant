'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input } from '@/components/Input';
import { VoiceCallWrapper } from '@/components/VoiceCallWrapper';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface Assistant {
  id: string;
  name: string;
  description: string | null;
  tts_provider: string;
  voice_id: string;
  model: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  call_count: number;
}

interface VoiceClone {
  id: string;
  voice_name: string;
  display_name: string;
  is_public: boolean;
}

interface TTSVoice {
  id: string;
  name: string;
  gender: string;
  accent?: string;
  is_user_clone: boolean;
}

// TTS Provider configuration (static fallback if API unavailable)
const TTS_PROVIDERS: Record<string, {
  name: string;
  latency: string;
  description: string;
  voices: { id: string; name: string; gender: string; accent?: string }[];
}> = {
  cartesia: {
    name: "Cartesia",
    latency: "~30ms",
    description: "Ultra-low latency, recommended for real-time voice",
    voices: [
      { id: "a0e99841-438c-4a64-b679-ae501e7d6091", name: "Barbershop Man", gender: "male", accent: "US" },
      { id: "156fb8d2-335b-4950-9cb3-a2d33f91d3f1", name: "Classy British Man", gender: "male", accent: "UK" },
      { id: "638efaaa-4d0c-442e-b701-3fae16aad012", name: "Confident British Man", gender: "male", accent: "UK" },
      { id: "ee7ea9f8-c0c1-498c-9f62-dc2f7b5dc78f", name: "Doctor Mischief", gender: "male", accent: "US" },
      { id: "95856005-0332-41b0-935f-352e296aa0df", name: "Movieman", gender: "male", accent: "US" },
      { id: "36b42fcb-60c5-4bec-b077-cb1a00a92ec6", name: "Newsman", gender: "male", accent: "US" },
      { id: "726d5ae5-055f-4c3d-8355-d9677de68571", name: "Nonfiction Man", gender: "male", accent: "US" },
      { id: "5c42302c-194b-4d0c-ba1a-8cb485c84ab9", name: "Reading Man", gender: "male", accent: "US" },
      { id: "fb26447f-308b-471e-8b00-8b39d669f8d6", name: "Sportsman", gender: "male", accent: "US" },
      { id: "d46abd1d-2571-4e77-a5c1-ca0ad9382e28", name: "Teacher Lady", gender: "female", accent: "US" },
      { id: "c45bc5ec-dc68-4feb-8829-6e6b2748095d", name: "Wise Lady", gender: "female", accent: "US" },
      { id: "c2ac25f9-ecc4-4f56-9095-651354df60c0", name: "Commercial Lady", gender: "female", accent: "US" },
      { id: "e00d0e4c-a5c8-443f-a8a3-473eb9a62355", name: "Maria", gender: "female", accent: "US" },
      { id: "f786b574-daa5-4673-aa0c-cbe3e8534c02", name: "Katie (Default)", gender: "female", accent: "US" },
    ],
  },
  elevenlabs: {
    name: "ElevenLabs",
    latency: "~150ms",
    description: "Premium quality, expressive voices",
    voices: [
      { id: "21m00Tcm4TlvDq8ikWAM", name: "Rachel", gender: "female", accent: "US" },
      { id: "AZnzlk1XvdvUeBnXmlld", name: "Domi", gender: "female", accent: "US" },
      { id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", gender: "female", accent: "US" },
      { id: "ErXwobaYiN019PkySvjV", name: "Antoni", gender: "male", accent: "US" },
      { id: "MF3mGyEYCl7XYWbV9V6O", name: "Elli", gender: "female", accent: "US" },
      { id: "TxGEqnHWrfWFTfGW9XjX", name: "Josh", gender: "male", accent: "US" },
      { id: "VR6AewLTigWG4xSOukaG", name: "Arnold", gender: "male", accent: "US" },
      { id: "pNInz6obpgDQGcFmaJgB", name: "Adam", gender: "male", accent: "US" },
      { id: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", gender: "male", accent: "US" },
      { id: "jBpfuIE2acCO8z3wKNLl", name: "Gigi", gender: "female", accent: "US" },
      { id: "oWAxZDx7w5VEj9dCyTzz", name: "Grace", gender: "female", accent: "US" },
      { id: "onwK4e9ZLuTAKqWW03F9", name: "Daniel", gender: "male", accent: "UK" },
      { id: "pqHfZKP75CvOlQylNhV4", name: "Bill", gender: "male", accent: "US" },
      { id: "nPczCjzI2devNBz1zQrb", name: "Brian", gender: "male", accent: "US" },
      { id: "N2lVS1w4EtoT3dr4eOWO", name: "Callum", gender: "male", accent: "UK" },
      { id: "IKne3meq5aSn9XLyUdCD", name: "Charlie", gender: "male", accent: "AU" },
    ],
  },
  deepgram: {
    name: "Deepgram Aura",
    latency: "~80ms",
    description: "Fast, natural voices (same provider as STT)",
    voices: [
      { id: "aura-asteria-en", name: "Asteria", gender: "female", accent: "US" },
      { id: "aura-luna-en", name: "Luna", gender: "female", accent: "US" },
      { id: "aura-stella-en", name: "Stella", gender: "female", accent: "US" },
      { id: "aura-athena-en", name: "Athena", gender: "female", accent: "UK" },
      { id: "aura-hera-en", name: "Hera", gender: "female", accent: "US" },
      { id: "aura-orion-en", name: "Orion", gender: "male", accent: "US" },
      { id: "aura-arcas-en", name: "Arcas", gender: "male", accent: "US" },
      { id: "aura-perseus-en", name: "Perseus", gender: "male", accent: "US" },
      { id: "aura-angus-en", name: "Angus", gender: "male", accent: "Ireland" },
      { id: "aura-orpheus-en", name: "Orpheus", gender: "male", accent: "US" },
      { id: "aura-helios-en", name: "Helios", gender: "male", accent: "UK" },
      { id: "aura-zeus-en", name: "Zeus", gender: "male", accent: "US" },
    ],
  },
  openai: {
    name: "OpenAI",
    latency: "~200ms",
    description: "GPT-powered synthesis, consistent quality",
    voices: [
      { id: "alloy", name: "Alloy", gender: "neutral", accent: "US" },
      { id: "echo", name: "Echo", gender: "male", accent: "US" },
      { id: "fable", name: "Fable", gender: "male", accent: "UK" },
      { id: "onyx", name: "Onyx", gender: "male", accent: "US" },
      { id: "nova", name: "Nova", gender: "female", accent: "US" },
      { id: "shimmer", name: "Shimmer", gender: "female", accent: "US" },
    ],
  },
  coqui: {
    name: "Coqui XTTS (Free)",
    latency: "~150ms",
    description: "Free voice cloning - use your own voice!",
    voices: [
      { id: "default", name: "Clone Your Voice First", gender: "neutral", accent: "Any" },
    ],
  },
  kokoro: {
    name: "Kokoro (Free)",
    latency: "~100ms",
    description: "Free 82M model - 22 voices, multi-language!",
    voices: [
      // US English
      { id: "af_heart", name: "Heart", gender: "female", accent: "US" },
      { id: "af_bella", name: "Bella", gender: "female", accent: "US" },
      { id: "af_sarah", name: "Sarah", gender: "female", accent: "US" },
      { id: "af_nicole", name: "Nicole", gender: "female", accent: "US" },
      { id: "af_sky", name: "Sky", gender: "female", accent: "US" },
      { id: "am_adam", name: "Adam", gender: "male", accent: "US" },
      { id: "am_michael", name: "Michael", gender: "male", accent: "US" },
      { id: "am_fenrir", name: "Fenrir", gender: "male", accent: "US" },
      // British English
      { id: "bf_emma", name: "Emma", gender: "female", accent: "UK" },
      { id: "bf_isabella", name: "Isabella", gender: "female", accent: "UK" },
      { id: "bf_alice", name: "Alice", gender: "female", accent: "UK" },
      { id: "bf_lily", name: "Lily", gender: "female", accent: "UK" },
      { id: "bm_george", name: "George", gender: "male", accent: "UK" },
      { id: "bm_lewis", name: "Lewis", gender: "male", accent: "UK" },
      { id: "bm_daniel", name: "Daniel", gender: "male", accent: "UK" },
      // Other languages
      { id: "ef_dora", name: "Dora", gender: "female", accent: "Spanish" },
      { id: "em_alex", name: "Alex", gender: "male", accent: "Spanish" },
      { id: "ff_siwis", name: "Siwis", gender: "female", accent: "French" },
      { id: "jf_alpha", name: "Alpha", gender: "female", accent: "Japanese" },
      { id: "jm_kumo", name: "Kumo", gender: "male", accent: "Japanese" },
      { id: "zf_xiaobei", name: "Xiaobei", gender: "female", accent: "Chinese" },
      { id: "zm_yunjian", name: "Yunjian", gender: "male", accent: "Chinese" },
    ],
  },
};

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
  const [loadingEdit, setLoadingEdit] = useState(false);
  const [activeCall, setActiveCall] = useState<{ id: string; name: string } | null>(null);

  // Template selection
  const [selectedTemplate, setSelectedTemplate] = useState('custom');

  // Voice clones
  const [voiceClones, setVoiceClones] = useState<VoiceClone[]>([]);

  // Dynamic voices from API
  const [providerVoices, setProviderVoices] = useState<TTSVoice[]>([]);
  const [userVoiceClones, setUserVoiceClones] = useState<TTSVoice[]>([]);
  const [loadingVoices, setLoadingVoices] = useState(false);

  // LLM Providers with API documentation links
  const LLM_PROVIDERS: Record<string, {
    name: string;
    api_docs: string;
    api_keys_url: string;
    models: { id: string; name: string; context: string; speed: string }[];
    default_model: string;
  }> = {
    groq: {
      name: "Groq (Ultra Fast)",
      api_docs: "https://console.groq.com/docs/api-reference",
      api_keys_url: "https://console.groq.com/keys",
      models: [
        { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B (Best)", context: "128K", speed: "fastest" },
        { id: "llama-3.1-70b-versatile", name: "Llama 3.1 70B", context: "128K", speed: "fastest" },
        { id: "llama-3.1-8b-instant", name: "Llama 3.1 8B (Instant)", context: "128K", speed: "fastest" },
        { id: "mixtral-8x7b-32768", name: "Mixtral 8x7B", context: "32K", speed: "fastest" },
      ],
      default_model: "llama-3.3-70b-versatile",
    },
    anthropic: {
      name: "Anthropic (Claude)",
      api_docs: "https://docs.anthropic.com/en/api/getting-started",
      api_keys_url: "https://console.anthropic.com/settings/keys",
      models: [
        { id: "claude-sonnet-4-5-20250929", name: "Claude Sonnet 4.5 (Latest)", context: "200K", speed: "fast" },
        { id: "claude-opus-4-5-20251101", name: "Claude Opus 4.5 (Smartest)", context: "200K", speed: "medium" },
        { id: "claude-haiku-4-5-20241022", name: "Claude Haiku 4.5 (Fastest)", context: "200K", speed: "fastest" },
      ],
      default_model: "claude-sonnet-4-5-20250929",
    },
    openai: {
      name: "OpenAI (GPT)",
      api_docs: "https://platform.openai.com/docs/api-reference",
      api_keys_url: "https://platform.openai.com/api-keys",
      models: [
        { id: "gpt-4o", name: "GPT-4o (Latest)", context: "128K", speed: "fast" },
        { id: "gpt-4o-mini", name: "GPT-4o Mini (Fastest)", context: "128K", speed: "fastest" },
        { id: "gpt-4-turbo", name: "GPT-4 Turbo", context: "128K", speed: "medium" },
        { id: "o1-mini", name: "o1 Mini (Reasoning)", context: "128K", speed: "medium" },
      ],
      default_model: "gpt-4o",
    },
    google: {
      name: "Google (Gemini)",
      api_docs: "https://ai.google.dev/gemini-api/docs",
      api_keys_url: "https://aistudio.google.com/apikey",
      models: [
        { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash (Latest)", context: "1M", speed: "fastest" },
        { id: "gemini-1.5-pro", name: "Gemini 1.5 Pro", context: "2M", speed: "medium" },
        { id: "gemini-1.5-flash", name: "Gemini 1.5 Flash", context: "1M", speed: "fast" },
      ],
      default_model: "gemini-2.0-flash",
    },
    mistral: {
      name: "Mistral AI",
      api_docs: "https://docs.mistral.ai/api/",
      api_keys_url: "https://console.mistral.ai/api-keys/",
      models: [
        { id: "mistral-large-latest", name: "Mistral Large (Best)", context: "128K", speed: "medium" },
        { id: "mistral-small-latest", name: "Mistral Small (Fastest)", context: "32K", speed: "fastest" },
        { id: "codestral-latest", name: "Codestral (Code)", context: "32K", speed: "fast" },
      ],
      default_model: "mistral-large-latest",
    },
    together: {
      name: "Together AI",
      api_docs: "https://docs.together.ai/reference/completions",
      api_keys_url: "https://api.together.xyz/settings/api-keys",
      models: [
        { id: "meta-llama/Llama-3.3-70B-Instruct-Turbo", name: "Llama 3.3 70B Turbo", context: "128K", speed: "fast" },
        { id: "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", name: "Llama 3.1 405B", context: "128K", speed: "medium" },
        { id: "deepseek-ai/DeepSeek-R1-Distill-Llama-70B", name: "DeepSeek R1 70B", context: "64K", speed: "fast" },
      ],
      default_model: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    fireworks: {
      name: "Fireworks AI",
      api_docs: "https://docs.fireworks.ai/api-reference/introduction",
      api_keys_url: "https://fireworks.ai/account/api-keys",
      models: [
        { id: "accounts/fireworks/models/llama-v3p3-70b-instruct", name: "Llama 3.3 70B", context: "128K", speed: "fastest" },
        { id: "accounts/fireworks/models/llama-v3p1-405b-instruct", name: "Llama 3.1 405B", context: "128K", speed: "fast" },
      ],
      default_model: "accounts/fireworks/models/llama-v3p3-70b-instruct",
    },
    deepseek: {
      name: "DeepSeek",
      api_docs: "https://platform.deepseek.com/api-docs",
      api_keys_url: "https://platform.deepseek.com/api_keys",
      models: [
        { id: "deepseek-chat", name: "DeepSeek Chat (V3)", context: "64K", speed: "fast" },
        { id: "deepseek-reasoner", name: "DeepSeek R1 (Reasoning)", context: "64K", speed: "medium" },
      ],
      default_model: "deepseek-chat",
    },
    xai: {
      name: "xAI (Grok)",
      api_docs: "https://docs.x.ai/api",
      api_keys_url: "https://console.x.ai/",
      models: [
        { id: "grok-2-latest", name: "Grok 2 (Latest)", context: "128K", speed: "fast" },
        { id: "grok-2-vision-latest", name: "Grok 2 Vision", context: "32K", speed: "fast" },
      ],
      default_model: "grok-2-latest",
    },
    cohere: {
      name: "Cohere",
      api_docs: "https://docs.cohere.com/reference/chat",
      api_keys_url: "https://dashboard.cohere.com/api-keys",
      models: [
        { id: "command-r-plus", name: "Command R+ (Best)", context: "128K", speed: "medium" },
        { id: "command-r", name: "Command R", context: "128K", speed: "fast" },
      ],
      default_model: "command-r-plus",
    },
    perplexity: {
      name: "Perplexity (Online)",
      api_docs: "https://docs.perplexity.ai/api-reference/chat-completions",
      api_keys_url: "https://www.perplexity.ai/settings/api",
      models: [
        { id: "sonar-pro", name: "Sonar Pro (Best Online)", context: "200K", speed: "medium" },
        { id: "sonar", name: "Sonar (Online Search)", context: "127K", speed: "fast" },
      ],
      default_model: "sonar-pro",
    },
  };

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [ttsProvider, setTtsProvider] = useState('cartesia');
  const [voiceId, setVoiceId] = useState('f786b574-daa5-4673-aa0c-cbe3e8534c02'); // Katie default

  // Voice preview state
  const [previewingVoice, setPreviewingVoice] = useState(false);
  const [previewAudio, setPreviewAudio] = useState<HTMLAudioElement | null>(null);

  const previewVoice = async () => {
    if (previewingVoice || !voiceId) return;

    // Stop any existing preview
    if (previewAudio) {
      previewAudio.pause();
      previewAudio.currentTime = 0;
    }

    setPreviewingVoice(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/api/tts/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: ttsProvider,
          voice_id: voiceId,
          text: "Hello! This is how I sound. I hope you like my voice.",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const audio = new Audio(`data:${data.content_type};base64,${data.audio_base64}`);
        setPreviewAudio(audio);
        audio.play();
        audio.onended = () => setPreviewingVoice(false);
      } else {
        console.error('Preview failed:', await response.text());
        setPreviewingVoice(false);
      }
    } catch (error) {
      console.error('Preview error:', error);
      setPreviewingVoice(false);
    }
  };

  const [llmProvider, setLlmProvider] = useState('groq');
  const [model, setModel] = useState('llama-3.3-70b-versatile');
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

  // Voice control settings (competitive with Vapi/ElevenLabs)
  const [speechSpeed, setSpeechSpeed] = useState(0.9);
  const [responseDelayMs, setResponseDelayMs] = useState(400);
  const [punctuationPauseMs, setPunctuationPauseMs] = useState(300);
  const [noPunctuationPauseMs, setNoPunctuationPauseMs] = useState(1000);
  const [turnEagerness, setTurnEagerness] = useState('balanced');

  useEffect(() => {
    if (user?.id) {
      loadAssistants();
      loadVoiceClones();
      loadProviderVoices(ttsProvider);
    }
  }, [user?.id]);

  // Load voices when TTS provider changes
  useEffect(() => {
    if (user?.id) {
      loadProviderVoices(ttsProvider);
    }
  }, [ttsProvider, user?.id]);

  const loadVoiceClones = async () => {
    if (!user?.id) return;
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/voice-clones`, {
        headers: { 'X-User-ID': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setVoiceClones(data.voice_clones || []);
      }
    } catch (err) {
      console.error('Failed to load voice clones:', err);
    }
  };

  const loadProviderVoices = async (provider: string) => {
    if (!user?.id) return;
    setLoadingVoices(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/api/tts/voices/${provider}`, {
        headers: { 'X-User-ID': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setProviderVoices(data.voices || []);
        setUserVoiceClones(data.user_clones || []);
      } else {
        // Fallback to static voices if API fails
        const staticVoices = TTS_PROVIDERS[provider]?.voices || [];
        setProviderVoices(staticVoices.map(v => ({ ...v, is_user_clone: false })));
        setUserVoiceClones([]);
      }
    } catch (err) {
      console.error(`Failed to load ${provider} voices:`, err);
      // Fallback to static voices
      const staticVoices = TTS_PROVIDERS[provider]?.voices || [];
      setProviderVoices(staticVoices.map(v => ({ ...v, is_user_clone: false })));
      setUserVoiceClones([]);
    } finally {
      setLoadingVoices(false);
    }
  };

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

  // Handle edit button click
  const handleEdit = async (assistantId: string) => {
    if (!user?.id) return;
    setLoadingEdit(true);
    try {
      const response = await api.getAssistant(user.id, assistantId);
      const assistant = response.assistant;

      // Populate form with existing data
      setEditingId(assistantId);
      setName(assistant.name);
      setDescription(assistant.description || '');
      setSystemPrompt(assistant.system_prompt);
      setTtsProvider(assistant.tts_provider || 'cartesia');
      setVoiceId(assistant.voice_id || 'f786b574-daa5-4673-aa0c-cbe3e8534c02');
      setLlmProvider(assistant.llm_provider || 'groq');
      setModel(assistant.model || 'llama-3.3-70b-versatile');
      setTemperature(assistant.temperature ?? 0.7);
      setMaxTokens(assistant.max_tokens ?? 150);
      setFirstMessage(assistant.first_message || '');

      // Advanced settings - check both direct fields and metadata for backwards compatibility
      const meta = (assistant.metadata || {}) as Record<string, number | boolean | string>;
      const a = assistant as Record<string, unknown>;
      setVadSensitivity(typeof a.vad_sensitivity === 'number' ? a.vad_sensitivity : (typeof meta.vad_sensitivity === 'number' ? meta.vad_sensitivity : 0.5));
      setEndpointingMs(typeof a.endpointing_ms === 'number' ? a.endpointing_ms : (typeof meta.endpointing_ms === 'number' ? meta.endpointing_ms : 600));
      setEnableBargein(typeof a.enable_bargein === 'boolean' ? a.enable_bargein : (typeof meta.enable_bargein === 'boolean' ? meta.enable_bargein : true));
      setStreamingChunks(typeof a.streaming_chunks === 'boolean' ? a.streaming_chunks : (typeof meta.streaming_chunks === 'boolean' ? meta.streaming_chunks : true));
      setFirstMessageLatencyMs(typeof a.first_message_latency_ms === 'number' ? a.first_message_latency_ms : (typeof meta.first_message_latency_ms === 'number' ? meta.first_message_latency_ms : 800));
      setTurnDetectionMode(typeof a.turn_detection_mode === 'string' ? a.turn_detection_mode : (typeof meta.turn_detection_mode === 'string' ? meta.turn_detection_mode : 'server_vad'));

      // Voice control settings
      setSpeechSpeed(typeof a.speech_speed === 'number' ? a.speech_speed : 0.9);
      setResponseDelayMs(typeof a.response_delay_ms === 'number' ? a.response_delay_ms : 400);
      setPunctuationPauseMs(typeof a.punctuation_pause_ms === 'number' ? a.punctuation_pause_ms : 300);
      setNoPunctuationPauseMs(typeof a.no_punctuation_pause_ms === 'number' ? a.no_punctuation_pause_ms : 1000);
      setTurnEagerness(typeof a.turn_eagerness === 'string' ? a.turn_eagerness : 'balanced');

      setSelectedTemplate('custom');
      setShowCreate(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to load assistant details');
    } finally {
      setLoadingEdit(false);
    }
  };

  // Reset form to defaults
  const resetForm = () => {
    setName('');
    setDescription('');
    setSystemPrompt('');
    setTtsProvider('cartesia');
    setVoiceId('f786b574-daa5-4673-aa0c-cbe3e8534c02'); // Katie default
    setLlmProvider('groq');
    setModel('llama-3.3-70b-versatile');
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
    setSpeechSpeed(0.9);
    setResponseDelayMs(400);
    setPunctuationPauseMs(300);
    setNoPunctuationPauseMs(1000);
    setTurnEagerness('balanced');
    setSelectedTemplate('custom');
    setEditingId(null);
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

  const handleSave = async () => {
    if (!user?.id || !name.trim() || !systemPrompt.trim()) return;

    setCreating(true);
    try {
      const data = {
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        description: description.trim() || undefined,
        tts_provider: ttsProvider,
        voice_id: voiceId,
        llm_provider: llmProvider,
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
        // Voice control settings
        speech_speed: speechSpeed,
        response_delay_ms: responseDelayMs,
        punctuation_pause_ms: punctuationPauseMs,
        no_punctuation_pause_ms: noPunctuationPauseMs,
        turn_eagerness: turnEagerness,
      };

      if (editingId) {
        // Update existing assistant
        await api.updateAssistant(user.id, editingId, data);
      } else {
        // Create new assistant
        await api.createAssistant(user.id, data);
      }

      // Reset form and close
      resetForm();
      setShowCreate(false);

      // Reload list
      loadAssistants();
    } catch (err) {
      alert(err instanceof Error ? err.message : `Failed to ${editingId ? 'update' : 'create'} assistant`);
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

      {/* Create/Edit Form */}
      {showCreate && (
        <Card glow>
          <CardTitle>{editingId ? 'Edit Assistant' : 'Create New Assistant'}</CardTitle>
          <CardContent>
            <div className="space-y-4">
              {/* Quick Start Templates - only show for new assistants */}
              {!editingId && (
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
              )}

              {!editingId && <div className="border-t border-gold/10 pt-4" />}

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
              {/* TTS Provider & Voice Selection */}
              <div className="space-y-3 p-4 bg-oled-dark/50 rounded-lg border border-gold/20">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gold">Voice Settings</h4>
                  <span className="text-xs text-gray-500">
                    {TTS_PROVIDERS[ttsProvider]?.latency} latency
                  </span>
                </div>
                <p className="text-xs text-gray-500">
                  {TTS_PROVIDERS[ttsProvider]?.description}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {/* TTS Provider Dropdown */}
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Provider</label>
                    <select
                      value={ttsProvider}
                      onChange={(e) => {
                        const provider = e.target.value;
                        setTtsProvider(provider);
                        // Set default voice for the new provider
                        const firstVoice = TTS_PROVIDERS[provider]?.voices[0];
                        if (firstVoice) {
                          setVoiceId(firstVoice.id);
                        }
                      }}
                      className="w-full px-3 py-2 bg-oled-dark border border-gold/30 rounded-lg
                        text-white text-sm focus:outline-none focus:border-gold transition-colors"
                    >
                      <optgroup label="★ Free TTS">
                        <option value="kokoro">Kokoro - 22 Free Voices! (~100ms)</option>
                        <option value="coqui">Coqui XTTS - Clone Your Voice (~150ms)</option>
                      </optgroup>
                      <optgroup label="Recommended (Low Latency)">
                        <option value="cartesia">Cartesia (~30ms)</option>
                        <option value="deepgram">Deepgram Aura (~80ms)</option>
                      </optgroup>
                      <optgroup label="Premium Quality">
                        <option value="elevenlabs">ElevenLabs (~150ms)</option>
                        <option value="openai">OpenAI (~200ms)</option>
                      </optgroup>
                    </select>
                  </div>
                  {/* Voice Dropdown with Preview */}
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">
                      Voice {loadingVoices && <span className="text-gold">(loading...)</span>}
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={voiceId}
                        onChange={(e) => setVoiceId(e.target.value)}
                        disabled={loadingVoices}
                        className="flex-1 px-3 py-2 bg-oled-dark border border-gold/30 rounded-lg
                          text-white text-sm focus:outline-none focus:border-gold transition-colors
                          disabled:opacity-50"
                      >
                        {/* CUSTOM VOICES AT TOP - Clearly separated */}
                        {userVoiceClones.length > 0 && (
                          <optgroup label="★ MY CUSTOM VOICES">
                            {userVoiceClones.map((clone) => (
                              <option key={clone.id} value={clone.id}>
                                ★ {clone.name}
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {/* Separator option group */}
                        {userVoiceClones.length > 0 && providerVoices.length > 0 && (
                          <optgroup label="────────────────────"></optgroup>
                        )}
                        {/* PREDEFINED VOICES */}
                        {providerVoices.length === 0 && userVoiceClones.length === 0 && (
                          <option value="" disabled>
                            {ttsProvider === 'coqui' ? 'Clone a voice first (Voice Clones page)' : 'No voices available'}
                          </option>
                        )}
                        <optgroup label="Male Voices">
                          {providerVoices
                            .filter(v => v.gender === 'male')
                            .map((voice) => (
                              <option key={voice.id} value={voice.id}>
                                {voice.name} {voice.accent ? `(${voice.accent})` : ''}
                              </option>
                            ))}
                        </optgroup>
                        <optgroup label="Female Voices">
                          {providerVoices
                            .filter(v => v.gender === 'female')
                            .map((voice) => (
                              <option key={voice.id} value={voice.id}>
                                {voice.name} {voice.accent ? `(${voice.accent})` : ''}
                              </option>
                            ))}
                        </optgroup>
                        {providerVoices.some(v => v.gender === 'neutral') && (
                          <optgroup label="Neutral Voices">
                            {providerVoices
                              .filter(v => v.gender === 'neutral')
                              .map((voice) => (
                                <option key={voice.id} value={voice.id}>
                                  {voice.name} {voice.accent ? `(${voice.accent})` : ''}
                                </option>
                              ))}
                          </optgroup>
                        )}
                      </select>
                      {/* Preview Button */}
                      <button
                        type="button"
                        onClick={previewVoice}
                        disabled={previewingVoice || loadingVoices || !voiceId}
                        className="px-3 py-2 bg-gold/20 border border-gold/30 rounded-lg
                          text-gold text-sm hover:bg-gold/30 transition-colors
                          disabled:opacity-50 disabled:cursor-not-allowed
                          flex items-center gap-1"
                        title="Preview voice"
                      >
                        {previewingVoice ? (
                          <>
                            <svg className="w-4 h-4 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
                              <rect x="6" y="4" width="4" height="16" rx="1"/>
                              <rect x="14" y="4" width="4" height="16" rx="1"/>
                            </svg>
                            <span className="hidden sm:inline">Playing...</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M8 5v14l11-7z"/>
                            </svg>
                            <span className="hidden sm:inline">Preview</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="text-xs text-gray-500 flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${
                    ttsProvider === 'cartesia' ? 'bg-green-400' :
                    ttsProvider === 'deepgram' ? 'bg-green-400' :
                    ttsProvider === 'elevenlabs' ? 'bg-yellow-400' :
                    'bg-orange-400'
                  }`}></span>
                  {providerVoices.length + userVoiceClones.length} voices available
                  {userVoiceClones.length > 0 && ` (${userVoiceClones.length} custom)`}
                </div>
              </div>

              {/* LLM Provider & Model Selection */}
              <div className="space-y-3 p-4 bg-oled-dark/50 rounded-lg border border-gold/20">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gold">LLM Provider</h4>
                  <div className="flex items-center gap-3">
                    <a
                      href="/dashboard/settings"
                      className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Setup API Keys
                    </a>
                    {LLM_PROVIDERS[llmProvider] && (
                      <a
                        href={LLM_PROVIDERS[llmProvider].api_keys_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                      >
                        Get Key
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                    )}
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Configure your API keys in <a href="/dashboard/settings" className="text-amber-400 hover:underline">Settings</a> to use different LLM providers.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <select
                      value={llmProvider}
                      onChange={(e) => {
                        const provider = e.target.value;
                        setLlmProvider(provider);
                        // Set default model for selected provider
                        if (LLM_PROVIDERS[provider]) {
                          setModel(LLM_PROVIDERS[provider].default_model);
                        }
                      }}
                      className="w-full px-3 py-2 bg-oled-dark border border-gold/30 rounded-lg
                        text-white text-sm focus:outline-none focus:border-gold transition-colors"
                    >
                      <optgroup label="Recommended (Low Latency)">
                        <option value="groq">Groq (Ultra Fast)</option>
                        <option value="fireworks">Fireworks AI</option>
                        <option value="together">Together AI</option>
                      </optgroup>
                      <optgroup label="Premium Models">
                        <option value="anthropic">Anthropic (Claude)</option>
                        <option value="openai">OpenAI (GPT)</option>
                        <option value="google">Google (Gemini)</option>
                      </optgroup>
                      <optgroup label="Other Providers">
                        <option value="mistral">Mistral AI</option>
                        <option value="deepseek">DeepSeek</option>
                        <option value="xai">xAI (Grok)</option>
                        <option value="cohere">Cohere</option>
                        <option value="perplexity">Perplexity (Online)</option>
                      </optgroup>
                    </select>
                  </div>
                  <div>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full px-3 py-2 bg-oled-dark border border-gold/30 rounded-lg
                        text-white text-sm focus:outline-none focus:border-gold transition-colors"
                    >
                      {LLM_PROVIDERS[llmProvider]?.models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.context})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">
                    Speed: <span className={
                      LLM_PROVIDERS[llmProvider]?.models.find(m => m.id === model)?.speed === 'fastest' ? 'text-green-400' :
                      LLM_PROVIDERS[llmProvider]?.models.find(m => m.id === model)?.speed === 'fast' ? 'text-yellow-400' :
                      'text-orange-400'
                    }>
                      {LLM_PROVIDERS[llmProvider]?.models.find(m => m.id === model)?.speed || 'medium'}
                    </span>
                  </span>
                  <a
                    href={LLM_PROVIDERS[llmProvider]?.api_docs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-400 hover:text-gold flex items-center gap-1"
                  >
                    API Docs
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
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

                  {/* Voice Customization Section */}
                  <div className="border-t border-gold/10 pt-4 mt-4">
                    <h4 className="text-sm font-medium text-gold mb-3 flex items-center gap-2">
                      🎙️ Voice Customization
                      <span className="text-xs text-gray-500 font-normal">(Conversation Flow Settings)</span>
                    </h4>

                    <div className="grid grid-cols-2 gap-4">
                      {/* Speech Speed */}
                      <div>
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                          Speech Speed ({speechSpeed}x)
                          <div className="group relative">
                            <span className="cursor-help text-gold/60 hover:text-gold">ⓘ</span>
                            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-oled-dark border border-gold/30 rounded-lg text-xs text-gray-400 z-10">
                              Controls how quickly the assistant speaks. Values range from 0.7x (slower) to 1.2x (faster). Default 0.9x provides natural conversation pace.
                            </div>
                          </div>
                        </label>
                        <input
                          type="range"
                          min="0.7"
                          max="1.2"
                          step="0.05"
                          value={speechSpeed}
                          onChange={(e) => setSpeechSpeed(parseFloat(e.target.value))}
                          className="w-full accent-gold"
                        />
                        <div className="flex justify-between text-xs text-gray-500 mt-1">
                          <span>Slower</span>
                          <span>Faster</span>
                        </div>
                      </div>

                      {/* Turn Eagerness */}
                      <div>
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                          Turn Eagerness
                          <div className="group relative">
                            <span className="cursor-help text-gold/60 hover:text-gold">ⓘ</span>
                            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-oled-dark border border-gold/30 rounded-lg text-xs text-gray-400 z-10">
                              <strong>Low:</strong> Patient - waits longer before responding, ideal for collecting detailed info.<br/>
                              <strong>Balanced:</strong> Normal turn-taking for most scenarios.<br/>
                              <strong>High:</strong> Eager - responds quickly for fast-paced conversations.
                            </div>
                          </div>
                        </label>
                        <select
                          value={turnEagerness}
                          onChange={(e) => setTurnEagerness(e.target.value)}
                          className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                            text-white focus:outline-none focus:border-gold transition-colors"
                        >
                          <option value="low">Low (Patient) - For info collection</option>
                          <option value="balanced">Balanced (Normal)</option>
                          <option value="high">High (Eager) - Quick responses</option>
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mt-4">
                      {/* Response Delay */}
                      <div>
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                          Response Delay (ms)
                          <div className="group relative">
                            <span className="cursor-help text-gold/60 hover:text-gold">ⓘ</span>
                            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-oled-dark border border-gold/30 rounded-lg text-xs text-gray-400 z-10">
                              How long the assistant waits after user stops speaking before responding. Higher values (800ms+) give users more time to complete thoughts. Lower values (200ms) feel more responsive.
                            </div>
                          </div>
                        </label>
                        <input
                          type="number"
                          min="200"
                          max="2000"
                          step="100"
                          value={responseDelayMs}
                          onChange={(e) => setResponseDelayMs(parseInt(e.target.value))}
                          className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                            text-white focus:outline-none focus:border-gold transition-colors"
                        />
                      </div>

                      {/* Punctuation Pause */}
                      <div>
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                          Punctuation Pause (ms)
                          <div className="group relative">
                            <span className="cursor-help text-gold/60 hover:text-gold">ⓘ</span>
                            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-oled-dark border border-gold/30 rounded-lg text-xs text-gray-400 z-10">
                              Pause after detecting punctuation (period, question mark). Shorter pauses (200ms) for quick conversations, longer (500ms) for natural pacing.
                            </div>
                          </div>
                        </label>
                        <input
                          type="number"
                          min="100"
                          max="1000"
                          step="50"
                          value={punctuationPauseMs}
                          onChange={(e) => setPunctuationPauseMs(parseInt(e.target.value))}
                          className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                            text-white focus:outline-none focus:border-gold transition-colors"
                        />
                      </div>
                    </div>

                    <div className="mt-4">
                      {/* No Punctuation Pause */}
                      <div className="max-w-[calc(50%-0.5rem)]">
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                          No Punctuation Pause (ms)
                          <div className="group relative">
                            <span className="cursor-help text-gold/60 hover:text-gold">ⓘ</span>
                            <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-oled-dark border border-gold/30 rounded-lg text-xs text-gray-400 z-10">
                              Wait time when no punctuation is detected (user may still be speaking). Higher values (1500ms) prevent interrupting users mid-thought.
                            </div>
                          </div>
                        </label>
                        <input
                          type="number"
                          min="500"
                          max="3000"
                          step="100"
                          value={noPunctuationPauseMs}
                          onChange={(e) => setNoPunctuationPauseMs(parseInt(e.target.value))}
                          className="w-full px-4 py-2 bg-oled-dark border border-gold/30 rounded-lg
                            text-white focus:outline-none focus:border-gold transition-colors"
                        />
                      </div>
                    </div>

                    {/* Presets */}
                    <div className="mt-4 pt-4 border-t border-gold/10">
                      <label className="text-sm font-medium text-gray-300 mb-2 block">Quick Presets</label>
                      <div className="flex gap-2 flex-wrap">
                        <button
                          type="button"
                          onClick={() => {
                            setSpeechSpeed(0.85);
                            setResponseDelayMs(800);
                            setPunctuationPauseMs(400);
                            setNoPunctuationPauseMs(1500);
                            setTurnEagerness('low');
                          }}
                          className="px-3 py-1.5 text-xs border border-gold/30 rounded text-gray-300 hover:bg-gold/10 transition-colors"
                        >
                          📝 Info Collection
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSpeechSpeed(0.9);
                            setResponseDelayMs(400);
                            setPunctuationPauseMs(300);
                            setNoPunctuationPauseMs(1000);
                            setTurnEagerness('balanced');
                          }}
                          className="px-3 py-1.5 text-xs border border-gold/30 rounded text-gray-300 hover:bg-gold/10 transition-colors"
                        >
                          💬 Natural Conversation
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSpeechSpeed(1.0);
                            setResponseDelayMs(250);
                            setPunctuationPauseMs(200);
                            setNoPunctuationPauseMs(600);
                            setTurnEagerness('high');
                          }}
                          className="px-3 py-1.5 text-xs border border-gold/30 rounded text-gray-300 hover:bg-gold/10 transition-colors"
                        >
                          ⚡ Quick Responses
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSpeechSpeed(0.8);
                            setResponseDelayMs(1000);
                            setPunctuationPauseMs(500);
                            setNoPunctuationPauseMs(2000);
                            setTurnEagerness('low');
                          }}
                          className="px-3 py-1.5 text-xs border border-gold/30 rounded text-gray-300 hover:bg-gold/10 transition-colors"
                        >
                          🎓 Elderly/Patient
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <HoneycombButton
                  onClick={handleSave}
                  disabled={creating || !name.trim() || !systemPrompt.trim()}
                >
                  {creating
                    ? (editingId ? 'Saving...' : 'Creating...')
                    : (editingId ? 'Save Changes' : 'Create Assistant')}
                </HoneycombButton>
                <button
                  onClick={() => {
                    resetForm();
                    setShowCreate(false);
                  }}
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
                      <span>
                        Voice: {TTS_PROVIDERS[assistant.tts_provider || 'cartesia']?.voices.find(v => v.id === assistant.voice_id)?.name || assistant.voice_id?.substring(0, 8) + '...'}
                        <span className="text-gray-600 ml-1">({assistant.tts_provider || 'cartesia'})</span>
                      </span>
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
                      onClick={() => handleEdit(assistant.id)}
                      disabled={loadingEdit}
                      className="px-3 py-1.5 text-sm border border-blue-500/30 rounded
                        text-blue-400 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                    >
                      Edit
                    </button>
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

      {/* Voice Call - Side Panel */}
      {activeCall && user && (
        <VoiceCallWrapper
          assistantId={activeCall.id}
          assistantName={activeCall.name}
          userId={user.id}
          defaultMode="livekit"
          onClose={() => {
            setActiveCall(null);
            loadAssistants(); // Refresh to update call count
          }}
        />
      )}
    </div>
  );
}
