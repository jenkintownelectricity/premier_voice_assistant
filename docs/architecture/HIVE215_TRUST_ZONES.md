# HIVE215 Trust Zones

## Zone Map

```
+-----------------------------------------------------------+
|                    UNTRUSTED ZONE                          |
|                                                           |
|  [Browser UI]  [Mobile UI]  [Uploads]  [External APIs]   |
|                                                           |
+-------------------+---+---+---+---------------------------+
                    |   |   |   |
              Constraint Ports (validate, type, receipt)
                    |   |   |   |
+-------------------v---v---v---v---------------------------+
|                 PARTIALLY TRUSTED ZONE                     |
|                                                           |
|  [Deepgram STT]  [Groq/Claude LLM]  [Cartesia TTS]      |
|  [LiveKit Events]  [Supabase Data]                        |
|                                                           |
+-------------------+---+---+-------------------------------+
                    |   |   |
            Normalization Kernels (normalize, schema-validate)
                    |   |   |
+-------------------v---v---v-------------------------------+
|                   TRUSTED ZONE                             |
|                                                           |
|  [Domain Kernels]  [Execution Spine]  [Typed State]       |
|  [UTK Doctrine]  [Governance Schemas]  [Receipts]         |
|                                                           |
+-----------------------------------------------------------+
```

## Zone Definitions

### UNTRUSTED Zone

Components entirely outside the governance boundary. Data from these sources must be quarantined and fully validated before entering any processing pipeline.

| Component | Risk Profile | Entry Port |
|-----------|-------------|------------|
| Browser UI (web/) | User-controlled DOM, devtools access, replay attacks | `ui_ports/browser_intent_normalization_port.py` |
| Mobile UI (mobile/) | User-controlled app state, potential tampering | `ui_ports/browser_intent_normalization_port.py` |
| User Uploads | Arbitrary file content, potential malware | `upload_ports/upload_quarantine_port.py` |
| External APIs | Third-party responses, potential manipulation | `external_api_ports/external_api_normalization_port.py` |

### PARTIALLY TRUSTED Zone

Service providers that deliver useful data but operate outside governance. Their outputs require normalization and schema validation.

| Component | Risk Profile | Normalization |
|-----------|-------------|---------------|
| Deepgram STT | May mishear, partial results, confidence variance | Transcript normalization kernel (>= 0.30 confidence) |
| Groq Fast Brain | May hallucinate, semantic drift | LLM output typing port |
| Claude Deep Brain | May hallucinate, verbose responses | LLM output typing port |
| Cartesia TTS | May fail, malformed audio | Voice kernel adapter receipt |
| LiveKit | External session state, transport errors | Session kernel validation |
| Supabase | Stale data, injection risk | Supabase normalization port |

### TRUSTED Zone

Components within the governance boundary that have been formally typed and validated.

| Component | Guarantee |
|-----------|-----------|
| Domain Kernels | Typed inputs, typed outputs, explicit state transitions |
| Execution Spine | Only processes typed ActionEnvelopes from trusted sources |
| Typed State | Session and user state validated by respective kernels |
| UTK Doctrine | Immutable system identity and constraints |
| Governance Schemas | Frozen JSON Schema definitions for all boundary types |
| Receipts | Immutable audit records of all governance events |

## Zone Crossing Rules

1. Data trust level can only increase: UNTRUSTED -> PARTIALLY TRUSTED -> TRUSTED
2. Every zone crossing passes through a constraint port or normalization kernel
3. Every zone crossing emits a receipt
4. TRUSTED data that exits to an external service and returns must be re-validated
5. No data bypasses zone crossing validation -- there are no "fast paths" that skip trust checks
