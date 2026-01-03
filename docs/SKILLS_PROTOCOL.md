# HIVE215 Skills Protocol

> **Version 1.1** | Last Updated: January 2, 2026

This document defines the skills protocol for HIVE215 Voice AI Platform.

---

## Overview

HIVE215 supports two categories of AI skills:

| Category | Source | Availability | Use Case |
|----------|--------|--------------|----------|
| **HIVE Preloaded** | Built into HIVE215 | Always available | Standard business use cases |
| **Fast Brain Custom** | Fast Brain LPU | Requires `FAST_BRAIN_URL` | Custom/advanced skills |

---

## HIVE Preloaded Skills

These skills are built into HIVE215 and work without any external configuration.

### Available Skills

| Skill ID | Name | Description |
|----------|------|-------------|
| `default` | Default Assistant | General purpose voice assistant |
| `receptionist` | Receptionist | Business call handling, scheduling, inquiries |
| `electrician` | Electrician | Electrical service expertise, quotes, dispatch |
| `plumber` | Plumber | Plumbing service expertise, quotes, dispatch |
| `lawyer` | Legal Intake | Legal consultation intake, case screening |
| `solar` | Solar Sales | Solar consultation, savings calculations |
| `hvac` | HVAC Technician | Heating/cooling service, maintenance |
| `medical-office` | Medical Office | Appointments, prescription refills |

### How Preloaded Skills Work

1. Skills are defined in `backend/main.py` in the `hive_preloaded_skills` list
2. Each skill has a corresponding system prompt handled by the LLM
3. Skills are applied at the agent level via `fast_brain_skill` field

---

## Fast Brain Custom Skills

Custom skills require Fast Brain LPU (Modal deployment).

### Configuration

```env
FAST_BRAIN_URL=https://username--fast-brain-lpu-fastapi-app.modal.run
```

### Creating a Custom Skill

**Via API:**
```bash
curl -X POST https://your-api/api/fast-brain/skills \
  -H "Content-Type: application/json" \
  -H "X-User-ID: your-user-id" \
  -d '{
    "skill_id": "molasses-expert",
    "name": "Molasses Expert",
    "description": "Expert on molasses production and recipes",
    "system_prompt": "You are an expert on molasses...",
    "knowledge": ["Molasses types", "Production process"]
  }'
```

**Via Fast Brain Dashboard:**
1. Access Fast Brain at your Modal URL
2. Navigate to Skills management
3. Create skill with name, description, and system prompt

### Custom Skill Structure

```json
{
  "id": "skill-id",
  "name": "Display Name",
  "description": "What this skill does",
  "system_prompt": "You are a...",
  "knowledge": ["Topic 1", "Topic 2"],
  "version": "1.0"
}
```

---

## Construction Expert (Multi-Mode Skill)

> **Added:** January 2, 2026

A specialized multi-mode skill for roofing/construction that intelligently switches between three expertise modes.

### Skill IDs

| Skill | ID | Description |
|-------|-----|-------------|
| **Construction Expert (Unified)** | `construction_expert` | All three modes combined |
| **Construction Expert (Voice)** | `construction_expert_voice` | Brevity-optimized for voice |
| **The Detailer** | `the_detailer_specs` | Codes, specs, compliance |
| **The Estimator** | `the_estimator_quantities` | Quantities, calculations, BOMs |
| **The Eyes** | `the_eyes_spatial_analysis` | Drawing analysis, spatial relationships |

### Mode Details

**MODE 1 - THE DETAILER (Specs, Codes & Compliance)**
- ANSI, SPRI, ES-1, ASCE-7, FM standards
- Manufacturer warranties and requirements
- Code compliance verification

**MODE 2 - THE ESTIMATOR (Quantities & JSON Logic)**
- Square footage and linear footage calculations
- Waste factor calculations (10-15%)
- Bill of Materials (BOM) generation
- JSON-structured output for integrations

**MODE 3 - THE EYES (Spatial Relationships & Drawing Analysis)**
- Shop drawing interpretation
- Taper plan analysis for drainage
- Water flow and slope verification
- Spatial conflict detection

### Voice Optimization

For voice assistants using Construction Expert:

```
Max Tokens: 75-100
Temperature: 0.3-0.5
Response Style: Max 2 sentences, no bullet points
Follow-up: Ask clarifying questions instead of info dumps
```

---

## Skill Selection Flow

```
User creates/edits assistant
    ↓
Selects skill from dropdown
    ├── HIVE Preloaded (always visible)
    └── Fast Brain Custom (if configured)
    ↓
Skill ID saved to va_assistants.fast_brain_skill
    ↓
LiveKit agent reads skill on call start
    ↓
Skill-specific prompts applied to conversation
```

---

## API Endpoints

### List All Skills

```http
GET /api/fast-brain/skills
```

**Response:**
```json
{
  "skills": [...],
  "hive_preloaded": [
    {"id": "default", "name": "Default Assistant", "category": "hive_preloaded"}
  ],
  "fast_brain": [
    {"id": "custom-skill", "name": "Custom Skill", "category": "fast_brain"}
  ],
  "fast_brain_configured": true,
  "fast_brain_error": null
}
```

### Create Custom Skill

```http
POST /api/fast-brain/skills
Content-Type: application/json
X-User-ID: {user_id}

{
  "skill_id": "my-skill",
  "name": "My Skill",
  "description": "Description",
  "system_prompt": "You are..."
}
```

---

## Database Schema

```sql
-- Skill is stored in the assistant record
ALTER TABLE va_assistants
ADD COLUMN fast_brain_skill VARCHAR(100) DEFAULT 'default';
```

---

## Adding New Preloaded Skills

To add a new HIVE Preloaded skill:

1. Edit `backend/main.py`
2. Find `hive_preloaded_skills` list
3. Add new skill object:

```python
{
    "id": "new-skill-id",
    "name": "New Skill Name",
    "description": "What this skill does",
    "category": "hive_preloaded"
},
```

4. Deploy changes

---

## Best Practices

### Skill IDs
- Use lowercase with hyphens: `my-skill-name`
- Keep IDs short but descriptive
- Avoid special characters

### System Prompts
- Be specific about the role
- Include key knowledge areas
- Define response style and tone
- Set boundaries (what NOT to do)

### Example System Prompt

```
You are a professional receptionist for [Business Name].

Your responsibilities:
- Answer calls professionally
- Schedule appointments
- Answer common questions
- Take messages when needed

Tone: Warm, professional, helpful
Response length: Keep responses concise (2-3 sentences)

You should NOT:
- Provide medical/legal advice
- Share confidential information
- Transfer to unavailable staff
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Skills dropdown empty | API not responding | Check Railway deployment |
| Fast Brain skills missing | `FAST_BRAIN_URL` not set | Add env var in Railway |
| Skill not applying | `fast_brain_skill` column missing | Run migration 013 |
| Custom skill not saved | Fast Brain not responding | Check Modal deployment |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-01-02 | Added Construction Expert multi-mode skill, voice optimization guidelines |
| 1.0 | 2025-12-20 | Initial protocol with HIVE Preloaded and Fast Brain distinction |

---

*HIVE215 Voice AI Platform - Skills Protocol*
