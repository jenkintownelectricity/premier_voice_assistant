# V2 Adoption and Dual Birth Rule

## 1. Purpose

Some systems may predate a governed Domain OS and later be adopted into it without falsifying historical origin. This doctrine defines the rules for recording such adoption events while preserving historical truth.

## 2. Dual Birth Rule

An adopted repository may carry two birth events:

- **V1 Birth** — original creation context
- **V2 Birth** — governed OS admission event

Both birth events are recorded in the ValidKernel Registry. Neither replaces the other.

## 3. V1 Birth

V1 Birth records the historical origin of the repository:

- **origin** — who created the system
- **context** — the original creation context and purpose
- **historical_system_family** — the system family at the time of creation, if known

V1 Birth is written once and never modified by later adoption events.

## 4. V2 Birth

V2 Birth records the governed admission of the repository into a Domain OS:

- **admitted_to** — the Domain OS the repository is admitted into
- **adopted_parent** — the governed parent under which the repository is admitted
- **admission_type** — the method of admission (e.g., `owner_approved`)
- **doctrine_version** — the doctrine version under which admission occurred (e.g., `V2`)

V2 Birth introduces the `adopted_parent` relationship. This relationship exists only in the V2 birth record.

## 5. Historical Integrity Rule

- V1 birth preserves historical truth.
- V2 birth preserves governed adoption truth.
- V2 adoption must not overwrite or falsify V1 origin.
- `adopted_parent` exists in V2 birth and does not replace original history.
- No registry operation may merge, collapse, or flatten V1 and V2 into a single ambiguous record.

## 6. Lineage Protection Rule

- `grown_from` must not be rewritten merely to reflect later OS adoption.
- Adoption is not retroactive birth lineage.
- `grown_from` records actual architectural derivation at the time of creation.
- `adopted_parent` records governed admission at the time of adoption.
- These are distinct concepts and must remain distinct in the registry.

## 7. Scope Rule

This doctrine applies when:

- A repository predates a Domain OS.
- The repository is later admitted into that OS through audit and owner approval.
- The repository was not originally grown from or architecturally derived from a component of that OS.

Repositories that were originally created within a governed OS use standard birth lineage (`grown_from`) and do not require dual birth records.

## 8. Relationship to Registry

- **Governance** defines the rule (this document).
- **Registry** records the birth events (ValidKernel_Registry catalogs).
- Registry entries must conform to this doctrine.
- Registry consumers (including VKBUS) must interpret dual-birth records according to these rules.
