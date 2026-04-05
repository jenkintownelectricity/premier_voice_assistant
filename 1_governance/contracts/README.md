# Governance Contracts

Formal contracts between HIVE215 components and external systems.

## Contract Types

- **Inter-system contracts:** Define the API surface between HIVE215 and Fast Brain, between HIVE215 and browser clients, between HIVE215 and mobile clients.
- **Intra-system contracts:** Define the interface between domain kernels, between kernels and the execution spine, between constraint ports and service adapters.
- **Service contracts:** Define SLA expectations for external services (Groq, Deepgram, Cartesia, LiveKit, Supabase).

## Rules

1. Contracts are typed -- both request and response shapes are defined as JSON Schema or Python dataclasses.
2. Contract violations emit a failure receipt and trigger fail-closed behavior.
3. Contracts are versioned. Breaking changes require a new contract version.
