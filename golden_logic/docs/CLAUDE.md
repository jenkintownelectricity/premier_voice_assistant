# Project Context and AI Agent Instructions

> **Single source of truth for Claude** | Last Updated: January 2, 2026

This document ensures consistent and high-quality contributions to the HIVE215 Voice AI Platform repository.

---

## 1. Core Mandates (MUST ADHERE)

### 1.1. Atomic Commits
All changes must be organized into **atomic commits**. A single commit must contain only changes related to one logical unit of work (e.g., one feature, one bug fix, one refactor).

### 1.2. Commit Message Standard
Use the **Conventional Commits** standard.

**Format:** `type(scope): subject`

| Type | Use When |
|------|----------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change (no bug fix, no new feature) |
| `style` | Formatting only |
| `chore` | Build, dependencies, config |
| `test` | Adding or updating tests |

**Examples:**
```
feat(worker): Add Fast Brain LPU integration for sub-200ms responses
fix(railway): Use venv activation in start script for nixpacks
docs(visuals): Add Railway deployment strategy decision guide
refactor(agent): Migrate to LiveKit Agents SDK 1.x room_io API
```

### 1.3. No Quick Fixes
**"NO QUICK FIXES. REAL FIX. DON'T BE A LAZY AI."**

- Fix root causes, not symptoms
- Validate environment before assuming it's correct
- Fail fast with helpful error messages
- Document why something broke, not just how you fixed it
- **No workarounds** - production requires proper solutions

### 1.4. Context File Updates
If a major architectural decision is made, you **MUST** propose an update to this `CLAUDE.md` file in the same change request.

### 1.5. Local Validation
Always validate changes before committing:

```bash
# Check syntax
python -m py_compile backend/main.py
python -m py_compile backend/livekit_worker.py

# Run locally (requires .env)
uvicorn backend.main:app --reload --port 8000

# Worker (requires LiveKit credentials)
python backend/livekit_worker.py start
```

---

## 2. Project Overview

### 2.1. HIVE215 Voice AI Platform

A real-time voice AI assistant platform built on LiveKit, featuring multi-tier LLM intelligence and sub-second response times.

| Component | Location | Purpose | Run Command |
|-----------|----------|---------|-------------|
| **Web API** | `backend/main.py` | FastAPI server, token generation, health checks | `uvicorn backend.main:app --port 8000` |
| **Voice Worker** | `backend/livekit_worker.py` | LiveKit agent, STT/TTS/LLM pipeline | `python backend/livekit_worker.py start` |
| **Fast Brain** | Modal deployment | Groq LPU for <200ms LLM responses | Deployed on Modal |
| **Frontend** | `templates/` | Web interface for voice interaction | Served by FastAPI |

### 2.2. Key Reference Files

| File | Purpose | Read When |
|------|---------|-----------|
| `CLAUDE.md` | This file - AI instructions | Every session |
| `docs/visuals/index.html` | Visual documentation timeline | Understanding architecture |
| `nixpacks.toml` | Railway build configuration | Debugging deployment |
| `Procfile` | Service start commands | Deployment issues |
| `requirements.txt` | Python dependencies | Adding packages |

---

## 3. Architecture & Stack

### 3.1. Voice Pipeline

```
User Speech → Silero VAD → Iron Ear Stack → Deepgram STT → Fast Brain → Cartesia TTS → User Hears
                               │
                               ▼
                    ┌─────────────────────┐
                    │  IRON EAR STACK     │
                    ├─────────────────────┤
                    │ V1: Debounce        │ ← Door slams, coughs (<300ms)
                    │ V2: Speaker Locking │ ← Background voices (volume)
                    │ V3: Identity Lock   │ ← ML fingerprint (Resemblyzer)
                    └─────────────────────┘
```

### 3.1.1 Iron Ear Stack (Audio Filtering)

Multi-layer noise filtering system:

| Version | Feature | Problem Solved | Method |
|---------|---------|----------------|--------|
| **V1** | Debounce | Door slams, coughs | Require 300ms+ continuous speech |
| **V2** | Speaker Locking | Background TV, people | Volume fingerprint (60% threshold) |
| **V3** | Identity Lock | Imposters, similar voices | 256-dim Resemblyzer embeddings |

**Key Files:**
- `worker/turn_taking.py` - TurnManager with Iron Ear V1/V2
- `worker/identity_manager.py` - IdentityManager with Resemblyzer ML
- `worker/voice_agent.py` - VoiceAgent with honeypot methods

**Honey Pot Flow (V3):**
1. Agent asks: *"Could you tell me your name and what you're calling about?"*
2. User speaks 10-15 seconds
3. System extracts 256-dim voice embedding
4. Identity LOCKED - only matching voice accepted

### 3.2. LLM Intelligence Tiers (Fast Brain Dual-System)

Fast Brain uses **Kahneman's "Thinking, Fast and Slow"** architecture:

| System | Model | Latency | Use Case | % of Queries |
|--------|-------|---------|----------|--------------|
| **System 1 (Fast)** | Groq + Llama 3.3 70B | ~80ms | Simple queries, greetings, FAQs | 90% |
| **System 2 (Deep)** | Claude 3.5 Sonnet | ~2000ms | Complex analysis, calculations | 10% |
| **Fallback** | Groq (direct) | ~100ms | When Fast Brain unavailable | - |

**Key Innovation:** When System 2 is needed, Fast Brain returns a **filler phrase** first:
- Filler plays via TTS (~2-3s) while Claude processes
- Creates natural conversation flow with perceived sub-second latency
- Example: "Let me look into that for you..." → [Claude thinks] → "Based on your 850 kWh usage..."

**Skills System:**
- `receptionist` - General business inquiries
- `electrician` - Electrical service expertise
- `plumber` - Plumbing service expertise
- `lawyer` - Legal intake
- `solar` - Solar panel sales
- `tara-sales` - Product demos

**Construction Expert (Trio) - Multi-Mode Skill:**

A unified skill for roofing/construction that auto-switches between three modes:

| Mode | Skill ID | Specialty |
|------|----------|-----------|
| **MODE 1 - THE DETAILER** | `the_detailer_specs` | Codes, specs, ANSI, SPRI, ES-1, ASCE-7, FM, warranties |
| **MODE 2 - THE ESTIMATOR** | `the_estimator_quantities` | Calculations, LF, SF, quantities, waste factors, BOMs |
| **MODE 3 - THE EYES** | `the_eyes_spatial_analysis` | Drawings, taper plans, water flow, drainage, spatial conflicts |
| **UNIFIED** | `construction_expert` | All three modes combined |
| **VOICE OPTIMIZED** | `construction_expert_voice` | Brevity-focused for voice calls |

### 3.3. Infrastructure

| Layer | Technology | Notes |
|-------|------------|-------|
| Real-time Media | LiveKit Cloud | WebRTC, managed service |
| STT | Deepgram | Real-time transcription |
| TTS | Cartesia | Low-latency voice synthesis |
| VAD | Silero | Voice activity detection |
| Hosting | Railway | Web + Worker services |
| Build | Nixpacks | Python 3.11, venv for PEP 668 |
| Fast LLM | Modal | Groq LPU deployment |

### 3.4. Railway Deployment

**CRITICAL:** Nixpacks auto-detects FastAPI and ignores Procfile. Must use explicit `[start]` section.

```toml
# nixpacks.toml - REQUIRED for Railway
[start]
cmd = "bash scripts/start.sh"
```

**Services:**
- **Web**: FastAPI server (PORT from Railway)
- **Worker**: LiveKit agent (connects to LiveKit Cloud)

### 3.5. Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `LIVEKIT_URL` | Worker | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | Both | LiveKit authentication |
| `LIVEKIT_API_SECRET` | Both | LiveKit authentication |
| `DEEPGRAM_API_KEY` | Worker | STT service |
| `CARTESIA_API_KEY` | Worker | TTS service |
| `OPENAI_API_KEY` | Worker | LLM fallback |
| `SERVICE_TYPE` | Both | `web` or `worker` (Railway) |
| `FAST_BRAIN_URL` | Both | Modal Fast Brain endpoint |

### 3.6. Fast Brain Management

**Deployment Location:** `D:\APP_CENTRAL\fast_brain` (Windows) or Modal Cloud

**Commands (PowerShell with venv):**

```powershell
# Activate venv
.\venv\Scripts\Activate

# Deploy to Modal
modal deploy deploy_groq.py

# Check logs
modal app logs fast-brain-lpu

# List deployed apps
modal app list

# Test skills endpoint
curl.exe "https://jenkintownelectricity--fast-brain-lpu-fastapi-app.modal.run/v1/skills"
```

**Creating Skills via API:**

```powershell
# Create skill JSON
@'
{
  "skill_id": "your_skill_id",
  "name": "Your Skill Name",
  "description": "Description here",
  "system_prompt": "Your system prompt here"
}
'@ | Out-File -FilePath "skill.json" -Encoding utf8

# POST to Fast Brain
curl.exe -X POST "https://jenkintownelectricity--fast-brain-lpu-fastapi-app.modal.run/v1/skills" -H "Content-Type: application/json" -d "@skill.json"
```

**Voice Optimization Rules:**
- Max 2 sentences per response
- No lists or bullet points in voice skills
- Ask follow-up questions instead of info dumps
- Set Max Tokens to 75-100 for voice assistants
- Set Temperature to 0.3-0.5 for focused responses

---

## 4. Visual Documentation System

### 4.1. Dated HTML Files Convention

All visual documentation lives in `docs/visuals/` with dated filenames:

```
docs/visuals/
├── index.html                           # Timeline index (always update)
├── 2025-12-17_investor_pitch.html       # Business/investor docs
├── 2025-12-18_stack_architecture.html   # Technical architecture
├── 2025-12-18_how_it_works.html         # Deep dive explanations
└── 2025-12-18_railway_strategy.html     # Decision guides
```

### 4.2. Naming Convention

**Format:** `YYYY-MM-DD_descriptive_name.html`

| Prefix | Use For |
|--------|---------|
| `*_architecture*` | System diagrams, component relationships |
| `*_how_it_works*` | Technical deep dives, explanations |
| `*_strategy*` | Decision guides, option comparisons |
| `*_pitch*` | Business, investor, marketing |
| `*_troubleshooting*` | Debug guides, error resolution |

### 4.3. Creating New Visual Docs

When creating visual HTML documentation:

1. **Always use dated filename**: `2025-12-18_topic_name.html`
2. **Update index.html**: Add new entry to the timeline
3. **Use consistent styling**: Dark theme, accent colors, monospace code
4. **Make interactive**: Tabs, animations, clickable elements where helpful
5. **Include in commit**: `docs: Add [topic] visual documentation`

### 4.4. Index.html Structure

```html
<div class="doc-card">
    <div class="doc-date">December 18, 2025</div>
    <h2 class="doc-title"><a href="2025-12-18_filename.html">Title</a></h2>
    <p class="doc-desc">Description of what this doc covers.</p>
    <div class="doc-tags">
        <span class="tag architecture">Architecture</span>
        <span class="tag">Interactive</span>
    </div>
</div>
```

### 4.5. Why Visual Docs?

- **Quick comprehension**: Complex systems explained visually
- **Decision support**: Side-by-side comparisons with pros/cons
- **Onboarding**: New developers understand stack fast
- **Historical record**: Dated files show evolution of architecture
- **Investor-ready**: Professional presentation of technical work

---

## 5. Decision Log (ADR Summary)

| ID | Decision | Status | Date |
|----|----------|--------|------|
| ADR-001 | Use LiveKit Agents SDK 1.x with room_io API | Accepted | 2025-12-17 |
| ADR-002 | Nixpacks venv for PEP 668 compliance | Accepted | 2025-12-18 |
| ADR-003 | Tiered LLM: Fast Brain (Groq) → GPT-4 → Claude | Accepted | 2025-12-17 |
| ADR-004 | Start script with SERVICE_TYPE for Railway multi-service | Accepted | 2025-12-18 |
| ADR-005 | Visual docs in docs/visuals/ with dated filenames | Accepted | 2025-12-18 |
| ADR-006 | Multi-TTS provider selection (Gen 2 rebuild) | Accepted | 2025-12-20 |
| ADR-007 | Iron Ear V2: Speaker Locking (volume-based filtering) | Accepted | 2025-12-31 |
| ADR-008 | Iron Ear V3: Identity Lock with Resemblyzer embeddings | Accepted | 2025-12-31 |
| ADR-009 | Default VoiceCallWrapper to LiveKit mode | Accepted | 2025-12-31 |

---

## 6. Anti-Patterns to Avoid

| Anti-Pattern | Why | Do Instead |
|--------------|-----|------------|
| UI-only config | Not reproducible, not in git | Put all config in files |
| Ignoring nixpacks behavior | Causes deployment failures | Always set explicit `[start]` |
| Old LiveKit API (`VoicePipelineAgent`) | Deprecated in 1.x | Use `room_io` + `AgentSession` |
| Hardcoded secrets | Security risk | Use environment variables |
| Quick workarounds | Tech debt, user hates them | Fix root cause properly |
| Undated documentation | No history, hard to track | Always date HTML files |

---

## 7. Permanent AI Skills (Always Active)

### Skill 1: Commit Curator
All proposed changes must adhere to **Conventional Commits**:
- Structure output as small, logical commits
- Each commit = ONE logical unit of work
- Format: `type(scope): subject`

### Skill 2: Root Cause Fixer
- NO quick fixes or workarounds
- Investigate why something fails, not just what fails
- Document the root cause in commits and docs

### Skill 3: Visual Documenter
After significant changes:
- Create or update visual HTML documentation
- Use dated filenames: `YYYY-MM-DD_topic.html`
- Update `docs/visuals/index.html` timeline

### Skill 4: Deployment Aware
- Understand nixpacks auto-detection behavior
- Always verify Railway config in files, not UI
- Test start commands work with venv activation

---

## 8. Session Workflow

### 8.1. Starting a Session

1. Read `CLAUDE.md` (this file)
2. Check `docs/visuals/index.html` for recent documentation
3. Review recent commits: `git log --oneline -10`
4. Ask clarifying questions before starting work

### 8.2. During a Session

1. Use TodoWrite to track tasks
2. Commit atomic changes with conventional commits
3. Create visual docs for complex explanations
4. Document problems and solutions

### 8.3. Ending a Session

1. Ensure all changes are committed
2. Push to the designated branch
3. Update visual docs if architecture changed
4. Update this file if decisions were made

---

## 9. Common Commands

```bash
# Local development
uvicorn backend.main:app --reload --port 8000
python backend/livekit_worker.py start

# Check Railway deployment files
cat nixpacks.toml
cat Procfile
cat railway.toml

# Git workflow
git status
git log --oneline -10
git push -u origin <branch-name>

# Validate Python syntax
python -m py_compile backend/main.py
python -m py_compile backend/livekit_worker.py
```

---

## 10. File Structure

```
premier_voice_assistant/
├── CLAUDE.md                 # This file - AI instructions
├── backend/
│   ├── main.py              # FastAPI web server
│   └── livekit_worker.py    # Voice agent worker
├── templates/               # Frontend HTML
├── static/                  # CSS, JS assets
├── docs/
│   └── visuals/             # Visual HTML documentation
│       ├── index.html       # Timeline index
│       └── YYYY-MM-DD_*.html # Dated docs
├── scripts/
│   └── start.sh             # Railway start script
├── nixpacks.toml            # Railway/Nixpacks config
├── Procfile                 # Service definitions
├── railway.toml             # Railway deploy config
└── requirements.txt         # Python dependencies
```

---

## 11. Critical Dependencies & Version Pinning

> **READ THIS FIRST** - These versions are battle-tested. Don't change without understanding the dependency chain.

### 11.1. LiveKit Agents Stack (CRITICAL)

The LiveKit Agents SDK has strict version requirements. **All plugins must match the core version.**

| Package | Version | Why This Version |
|---------|---------|------------------|
| `livekit-agents` | **1.3.8** | Latest stable with `room_io` API |
| `livekit-plugins-deepgram` | **1.3.8** | Must match agents version |
| `livekit-plugins-cartesia` | **1.3.8** | Must match agents version |
| `livekit-plugins-openai` | **1.3.8** | Must match agents version |
| `livekit-plugins-anthropic` | **1.3.8** | Must match agents version |
| `livekit-plugins-elevenlabs` | **1.3.8** | Must match agents version (added Dec 20) |
| `livekit-plugins-silero` | **1.3.8** | Must match agents version |
| `livekit-plugins-turn-detector` | **1.3.8** | Must match agents version |
| `opentelemetry-api` | **>=1.39.0** | Required by livekit-agents 1.3.8 |
| `opentelemetry-sdk` | **>=1.39.0** | Required by livekit-agents 1.3.8 |

**Version History & Lessons Learned:**
- `1.1.7` - Missing `room_io` module (import error)
- `1.3.8` - Works, requires opentelemetry >=1.39.0
- `1.21.0` opentelemetry - BREAKS with livekit-agents 1.3.8 (conflict)

### 11.2. Dockerfile Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir 'livekit-agents[deepgram,cartesia,openai,silero]==1.3.8'

COPY . .
CMD ["bash", "scripts/start.sh"]
```

### 11.3. Railway Service Configuration

| Service | `SERVICE_TYPE` | Purpose |
|---------|----------------|---------|
| Web | `web` | FastAPI server, token generation, health checks |
| Worker | `worker` | LiveKit voice agent, STT/TTS/LLM pipeline |

**Required Environment Variables:**

| Variable | Web | Worker | Description |
|----------|-----|--------|-------------|
| `SERVICE_TYPE` | `web` | `worker` | Determines which service to start |
| `LIVEKIT_URL` | Yes | Yes | e.g., `wss://your-app.livekit.cloud` |
| `LIVEKIT_API_KEY` | Yes | Yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | Yes | Yes | LiveKit API secret |
| `DEEPGRAM_API_KEY` | No | Yes | STT service (also enables Deepgram TTS) |
| `CARTESIA_API_KEY` | No | Yes | TTS service (recommended) |
| `ELEVENLABS_API_KEY` | No | Yes | ElevenLabs TTS (optional, premium) |
| `GROQ_API_KEY` | No | Yes | LLM (Groq Llama) |
| `FAST_BRAIN_URL` | No | Yes | Modal-deployed Fast Brain endpoint |
| `DEFAULT_SKILL` | No | Yes | Fast Brain skill (default: `default`) |

### 11.4. Common Dependency Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `cannot import name 'room_io'` | livekit-agents too old | Update to 1.3.8 |
| `opentelemetry-api conflict` | Version mismatch | Use >=1.39.0 |
| `pip backtracking 19+ minutes` | Unpinned versions | Pin all livekit plugins |
| `uvicorn not found` | venv not activated | Use Dockerfile, not nixpacks |
| `Invalid value for '--port': '${PORT:-8000}'` | Custom Start Command in Railway | Clear the command, use Dockerfile CMD |

---

## 12. Railway Deployment (COMPLETED)

**Status:** Option B (Custom Dockerfile) implemented on December 18, 2025.

**Files Created:**
- [x] `Dockerfile` - Python 3.11-slim with ffmpeg, libopus
- [x] `scripts/start.sh` - SERVICE_TYPE routing
- [x] `railway.toml` - Simplified (no nixpacks builder)
- [x] `.nixpacks.toml.bak` - Archived (no longer needed)

**Railway UI Configuration (one-time):**
- Web service: `SERVICE_TYPE=web`
- Worker service: `SERVICE_TYPE=worker`
- **CRITICAL: Custom Start Command must be EMPTY** (see section 12.1)

### 12.1. Custom Start Command WARNING

**CRITICAL LESSON LEARNED (December 18, 2025):**

Railway's **Custom Start Command** in Settings → Deploy **OVERRIDES** the Dockerfile's `CMD`. If you have a custom start command set, Railway ignores your Dockerfile CMD completely.

**Symptom:** Changes to `scripts/start.sh` or Dockerfile CMD have no effect.

**Fix:**
1. Go to Railway service → Settings → Deploy
2. Find "Custom Start Command"
3. **DELETE the contents** (leave it empty)
4. Redeploy

| Service | Custom Start Command | Should Be |
|---------|---------------------|-----------|
| Web | `uvicorn backend.main:app...` | **EMPTY** |
| Worker | `python backend/livekit_worker.py start` | **EMPTY** |

When empty, Railway uses `CMD ["bash", "scripts/start.sh"]` from Dockerfile, which routes based on `SERVICE_TYPE`.

---

## 13. Backup Service Setup

### 13.1. Why Backup Services?

| Service | Risk if Single Instance Fails | Recommendation |
|---------|------------------------------|----------------|
| Web | API unavailable, no new calls | Optional backup |
| Worker | Voice calls fail immediately | Recommended backup |

### 13.2. Creating a Backup Worker

1. In Railway, duplicate the Worker service
2. Set `SERVICE_TYPE=worker`
3. Copy all required environment variables (LIVEKIT_*, DEEPGRAM_*, etc.)
4. LiveKit Cloud automatically load-balances between workers

### 13.3. Migrating Legacy Services

If you have old services from before the Dockerfile migration:

1. **Clear Custom Start Command** - Remove any `uvicorn ...` command
2. **Set `SERVICE_TYPE`** - `web` or `worker`
3. **Trigger redeploy** - Railway will use the Dockerfile

---

## 14. Developer Handoff Checklist

### Before Handoff:
- [x] All services deployed and healthy (December 18, 2025)
- [x] Environment variables documented
- [x] Visual documentation up to date
- [x] CLAUDE.md has current dependency versions
- [x] README.md has developer setup instructions
- [x] Custom Start Commands cleared in Railway

### Quick Start for New Developers:

```bash
# Clone
git clone https://github.com/jenkintownelectricity/premier_voice_assistant.git
cd premier_voice_assistant

# Install
pip install -r requirements.txt

# Run locally
uvicorn backend.main:app --reload --port 8000
python backend/livekit_worker.py start

# Deploy to Railway
# 1. Connect GitHub repo
# 2. Set SERVICE_TYPE=web for web service
# 3. Set SERVICE_TYPE=worker for worker service
# 4. CLEAR Custom Start Command (Settings → Deploy)
# 5. Add all required env vars
```

### Visual Documentation:
- See `docs/visuals/index.html` for architecture diagrams
- See `docs/visuals/2025-12-18_dependencies.html` for dependency flow

---

## 15. Git Merge Commands (PowerShell)

When providing merge commands, **ALWAYS** provide both options:

### Option 1: One-Liner (Copy-Paste Friendly)
```powershell
git fetch origin; git checkout main; git pull origin main; git merge origin/<branch-name>; git push origin main
```

### Option 2: Step-by-Step (If Issues Occur)
```powershell
# Step 1: Fetch latest from remote
git fetch origin

# Step 2: Switch to main branch
git checkout main

# Step 3: Pull latest main
git pull origin main

# Step 4: Merge feature branch
git merge origin/<branch-name>

# Step 5: Push to main
git push origin main
```

**Note:** PowerShell uses `;` to chain commands (not `&&` like bash).

---

*Last updated by Claude on December 31, 2025*
