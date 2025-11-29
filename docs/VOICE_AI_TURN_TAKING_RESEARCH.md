# Voice AI Turn-Taking Research Report
## State-of-the-Art Analysis (2024-2025)

*Research compiled for Premier Voice Assistant development*

---

## Executive Summary

Turn-taking is the critical challenge in conversational AI that determines whether a voice assistant feels natural or robotic. This report analyzes the latest technologies, industry leaders, and user preferences to inform our turn-taking model development.

**Key Finding:** The best systems combine multiple signals (prosody + semantics + timing) and achieve ~300ms response latency to match human conversation patterns.

---

## 1. Industry Leaders Analysis

### Vapi ($20M Series A, Dec 2024)
**What Users Love:**
- Sub-500ms voice-to-voice latency
- Natural interruption handling (barge-in)
- Backchanneling ("mm-hmm", "I see")
- BYO architecture (swap any provider)
- 100+ languages, 1M concurrent calls

**Key Features:**
| Feature | Implementation |
|---------|---------------|
| Turn Detection | Server VAD + silence thresholds |
| Response Time | <500ms voice-to-voice |
| Interruption | Graceful stop + context retention |
| Developers | 100,000+ |

**Sources:** [Vapi Review](https://softailed.com/blog/vapi-review), [Product Hunt](https://www.producthunt.com/products/vapi)

---

### Hume AI EVI (Empathic Voice Interface)
**What Users Love:**
- "It knows when I'm done" - prosody-based turn detection
- Emotional intelligence in responses
- Natural tone matching

**Key Innovation:** Uses prosody (pitch, rhythm, timbre) for turn detection instead of just silence.

**EVI 3 Performance (May 2025):**
| Metric | EVI 3 | GPT-4o |
|--------|-------|--------|
| Naturalness | Preferred | - |
| Empathy | Preferred | - |
| Interruption Handling | Preferred | - |
| Response Speed | ~300ms | ~300ms |

**Technical Approach:**
- Speech-to-speech foundation model
- Same model understands AND generates speech
- Processes "tune, rhythm, and timbre" for turn detection

**Sources:** [Hume EVI](https://www.hume.ai/empathic-voice-interface), [EVI Overview](https://dev.hume.ai/docs/empathic-voice-interface-evi/overview)

---

### OpenAI Realtime API
**Key Features:**
- ~300ms response time (human threshold)
- Automatic interruption handling with context rollback
- Emotion detection from tone
- Persistent WebSocket connection

**Turn Detection:**
- Built-in VAD-based turn detection
- Automatic state synchronization on interruption
- Configurable silence thresholds

**Pricing:** $0.06/min input, $0.24/min output

**Sources:** [Realtime API](https://openai.com/index/introducing-the-realtime-api/), [LiveKit Partnership](https://blog.livekit.io/openai-livekit-partnership-advanced-voice-realtime-api/)

---

### Cartesia Sonic-3 ($100M raised, Oct 2025)
**Industry's Fastest TTS:**
| Version | Latency |
|---------|---------|
| Sonic 1.0 | 90ms |
| Sonic 2.0 | 45ms |
| Sonic 3.0 | 40ms |

**Key Innovation:** State Space Models (SSMs) instead of Transformers
- More memory-efficient
- Lower latency
- Better for on-device deployment

**Features:**
- 42 languages
- Instant voice cloning (10 seconds)
- Emotion tags in text (`<laugh>`, `<sigh>`)
- 62% preferred over ElevenLabs in blind tests

**Sources:** [Cartesia Sonic](https://cartesia.ai/sonic), [State of Voice AI 2024](https://cartesia.ai/blog/state-of-voice-ai-2024)

---

## 2. Cutting-Edge Turn-Taking Methods

### Method 1: Full-Duplex Speech-to-Speech (Kyutai Moshi)
**Revolutionary Approach:** Eliminates traditional turn-taking entirely.

```
Traditional: User speaks → Silence → Assistant speaks → Silence → ...
Moshi:       Always listening AND always generating (speech or silence)
```

**Technical Details:**
- Models user and AI speech in parallel streams
- 160ms theoretical latency (200ms practical)
- Handles overlapping speech natively
- Open source on Hugging Face

**Architecture:**
- Text LLM backbone
- Neural audio codec (Mimi) for speech tokens
- Dual-stream output (user echo + assistant speech)

**Sources:** [Moshi Paper](https://arxiv.org/abs/2410.00037), [Hugging Face](https://huggingface.co/papers/2410.00037)

---

### Method 2: Audio-Only Turn Detection (Krisp)
**Lightweight prosody-based approach:**

**Signals Used:**
- Pitch contour (falling = statement end)
- Energy levels (drop = utterance end)
- Speaking rate (slowing = completion)
- Pause patterns

**Advantages:**
- No transcription latency
- 6M parameters (lightweight)
- Edge-deployable
- Works across languages

**Sources:** [Krisp Turn-Taking](https://krisp.ai/blog/turn-taking-for-voice-ai/)

---

### Method 3: Semantic EOU Model (LiveKit)
**Transformer-based content analysis:**

**Model:** 135M parameter transformer (SmolLM v2 fine-tuned)

**How It Works:**
1. Analyze transcript content in real-time
2. Predict probability of utterance completion
3. Dynamically adjust silence timeout

**Results:**
- Significantly fewer interruptions
- No responsiveness sacrifice
- Works with existing VAD

**Configuration:**
```python
min_endpointing_delay = 0.5s  # Minimum wait
max_endpointing_delay = 3.0s  # Maximum wait
# Model predictions adjust within this range
```

**Sources:** [LiveKit EOU](https://blog.livekit.io/using-a-transformer-to-improve-end-of-turn-detection/), [Documentation](https://docs.livekit.io/agents/build/turns/)

---

### Method 4: Multimodal Fusion (Emerging)
**Combines all signals:**

```
Audio Signals          Text Signals           Context Signals
- Pitch contour        - Sentence completion  - Conversation history
- Energy levels        - Question detection   - Topic tracking
- Speaking rate        - Hesitation markers   - User profile
- Pause patterns       - Incomplete phrases   - Time of day
      ↓                       ↓                      ↓
      └───────────────────────┴──────────────────────┘
                              ↓
                    Weighted Confidence Score
                              ↓
                    Turn Prediction + Delay
```

---

## 3. Talk-Time Ratio Analytics (Rilla Voice)

**Key Research Finding:** Optimal assistant talk-time is 45-65% of conversation.

**Rilla's Data:**
- Largest dataset of in-person sales conversations
- 20+ million conversations analyzed
- Top performers: 45-65% talk time
- Top performers: 5x more open-ended questions

**Metrics Tracked:**
| Metric | Purpose |
|--------|---------|
| Talk-time ratio | Balance indicator |
| Questions asked | Engagement level |
| Interruption count | Conversation quality |
| Average turn length | Pacing |

**Sources:** [Rilla Voice](https://www.rilla.com/rilla-wild/how-to-use-ai-analytics-to-improve-sales-w-rilla-voice)

---

## 4. Awards & Recognition (2024-2025)

### CES 2025
- **SoundHound AI**: First in-vehicle voice commerce
- **Gaudio Lab**: 3rd consecutive CES Innovation Award (AI audio)

### SXSW 2024
- AI Voice & Robotics Pitch Competition
- Gaudio Lab: Innovation Awards Finalist

### Industry Recognition
- **Vapi**: $20M Series A from Bessemer Venture Partners
- **Cartesia**: $100M from Kleiner Perkins, NVIDIA
- **Hume AI**: $50M Series B

---

## 5. What Users Absolutely Love

Based on reviews across platforms:

### Top 7 User Preferences

| Rank | Feature | Why It Matters |
|------|---------|----------------|
| 1 | **"It knows when I'm done"** | Smart end-of-turn detection reduces frustration |
| 2 | **"No awkward pauses"** | Sub-300ms feels human |
| 3 | **"I can interrupt naturally"** | Graceful barge-in = control |
| 4 | **"It sounds like it cares"** | Emotional/empathic responses |
| 5 | **"Works in my language"** | Multilingual support |
| 6 | **"Easy to customize"** | Developer-friendly APIs |
| 7 | **"Scales without breaking"** | Enterprise reliability |

### User Complaints to Avoid

1. "It keeps cutting me off" - Too aggressive turn detection
2. "It waits too long" - High silence thresholds
3. "It sounds robotic" - No emotional matching
4. "It doesn't understand I'm thinking" - No hesitation detection
5. "It talks too much" - No talk-time awareness

---

## 6. Performance Benchmarks

### Current State (2024-2025)

| Component | Human | Best-in-Class | Our Target |
|-----------|-------|---------------|------------|
| Response latency | ~230ms | ~300ms | <300ms |
| Full stack (STT→LLM→TTS) | - | ~510ms | <400ms |
| TTS latency | - | 40ms (Cartesia) | <50ms |
| False interruption rate | ~5% | ~15-20% | <10% |

### Stack Breakdown (Cartesia State of Voice AI 2024)
```
Deepgram STT:  100ms
GPT-4:         320ms
Cartesia TTS:   90ms
─────────────────────
Total:         510ms
```

**Target for 2025:** <400ms with better turn detection

---

## 7. Implementation Recommendations

Based on this research, our turn-taking model should include:

### Feature 1: Prosody Analysis
- Track pitch contour (falling = completion)
- Monitor energy levels (drop = end)
- Analyze speaking rate (slowing = ending)

### Feature 2: Semantic EOU Model
- Detect sentence completion
- Identify questions (quick response)
- Recognize hesitation markers (wait)
- Detect incomplete indicators (wait)

### Feature 3: Dynamic Silence Thresholds
- High confidence → short threshold
- Low confidence → long threshold
- Prosody adjustments (pitch/energy)

### Feature 4: False Interruption Recovery
- Detect zero-word interruptions
- Resume from interrupted position
- Track interruption patterns

### Feature 5: Emotional Matching
- Detect user emotion from text + prosody
- Match response tone appropriately
- De-escalate frustration, match excitement

### Feature 6: Talk-Time Ratio Tracking
- Target 45-65% assistant ratio
- Adjust response length dynamically
- Track questions and interruptions

---

## 8. Technology Comparison Matrix

| Feature | Vapi | Hume EVI | OpenAI | Our Model |
|---------|------|----------|--------|-----------|
| Prosody Detection | Basic | Advanced | Basic | Advanced |
| Semantic EOU | Yes | Yes | Yes | Yes |
| Dynamic Thresholds | No | Yes | No | Yes |
| False Interrupt Recovery | No | No | Yes | Yes |
| Emotional Matching | No | Yes | Basic | Yes |
| Talk-Time Tracking | No | No | No | Yes |
| Response Time | <500ms | ~300ms | ~300ms | <300ms |

---

## 9. Market Growth

- **2024:** $12.24B conversational AI market
- **2025:** $14.29B projected
- **2030:** $41.39B projected (23.7% CAGR)
- **2032:** $61.69B projected

**Key Trend:** Evolution from chatbots to autonomous agents (30% of new apps by 2026 per Gartner)

---

## 10. References

### Industry Leaders
- [Vapi](https://vapi.ai/)
- [Hume AI](https://www.hume.ai/)
- [Cartesia](https://cartesia.ai/)
- [LiveKit](https://livekit.io/)
- [Rilla Voice](https://www.rilla.com/)

### Research Papers
- [Moshi: Speech-Text Foundation Model](https://arxiv.org/abs/2410.00037)
- [Voice Activity Projection (Stanford)](https://hai.stanford.edu/news/it-my-turn-yet-teaching-voice-assistant-when-speak)

### Documentation
- [LiveKit Turn Detection](https://docs.livekit.io/agents/build/turns/)
- [Hume EVI Docs](https://dev.hume.ai/docs/empathic-voice-interface-evi/overview)
- [OpenAI Realtime API](https://openai.com/index/introducing-the-realtime-api/)

---

*Document created: November 2025*
*For Premier Voice Assistant Development Team*
