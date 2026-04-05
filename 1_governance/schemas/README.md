# Governance Schemas

JSON Schema definitions for all typed data crossing HIVE215 system boundaries.

## Schemas

| Schema | Trust Level | Purpose |
|--------|-------------|---------|
| `transcript_normalized.schema.json` | Input: PARTIALLY TRUSTED | Typed transcript after STT normalization |
| `session_state.schema.json` | TRUSTED (after validation) | Typed session state with validated transitions |
| `ui_command.schema.json` | Input: UNTRUSTED | Browser UI commands requiring full validation |
| `upload_evidence.schema.json` | Input: UNTRUSTED | Upload metadata after quarantine |
| `adapter_receipt.schema.json` | Output: TRUSTED | Receipt from service adapter boundary crossing |
| `execution_receipt.schema.json` | Output: TRUSTED | Receipt from execution spine |
| `external_response_normalized.schema.json` | Input: UNTRUSTED | Normalized external API response |
| `supabase_payload_normalized.schema.json` | Input: PARTIALLY TRUSTED | Normalized Supabase payload |
| `worker_action_request.schema.json` | Internal: TRUSTED | Typed action request for worker execution |

## Rules

1. Every constraint port validates input against its declared schema.
2. Schema violations trigger fail-closed behavior.
3. Schemas are versioned and frozen once deployed.
