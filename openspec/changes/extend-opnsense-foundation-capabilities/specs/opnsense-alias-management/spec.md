## MODIFIED Requirements

### Requirement: Alias reload after successful changes
The system SHALL activate the fixed OPNsense alias target after successful declared changes and support an explicit activation-recovery retry independent of CRUD change detection.

#### Scenario: Alias apply succeeds
- **WHEN** declared create, update or removal operations complete successfully with actual changes
- **THEN** the workflow SHALL reload the alias target once and report whether activation succeeded

#### Scenario: Ordinary reconciliation makes no changes
- **WHEN** reconciliation makes no changes and opnsense_force_reload is false or omitted
- **THEN** the workflow SHALL NOT perform an unnecessary reload

#### Scenario: Operator retries failed activation
- **WHEN** a previous invocation saved configuration but failed activation and the caller explicitly sets opnsense_force_reload to true
- **THEN** successful admission and reconciliation SHALL reload the same fixed target even when CRUD returns no changes
- **AND** failed activation SHALL return nonzero with saved-versus-active status and retry guidance
- **AND** the workflow SHALL NOT infer rollback or successful data-plane behavior

#### Scenario: Check mode or partial CRUD failure occurs
- **WHEN** the workflow is in check mode or a declared write fails
- **THEN** it SHALL NOT activate configuration
- **AND** a write failure SHALL report that partial configuration changes may remain without claiming success

## ADDED Requirements

### Requirement: Generic URL table aliases
The system SHALL support caller-owned `urltable` alias declarations through the existing alias workflow, preserving its credential, additive ownership and reload boundaries.

#### Scenario: Declare a periodically refreshed URL table
- **WHEN** a present alias has type `urltable`, nonempty absolute HTTP(S) URL content and a decimal-string `updatefreq_days` of at least 0.1 days with at most one fractional digit and a finite, unchanged numeric round-trip through the pinned Collection
- **THEN** the workflow SHALL pass the declaration and refresh frequency to the pinned Collection
- **AND** OPNsense SHALL own fetching and periodic refresh without an IaaS scheduler or list provider default
- **AND** successful configuration SHALL NOT be reported as proof of successful table population

#### Scenario: Caller owns source selection
- **WHEN** a caller selects URLs, alias names or consumers
- **THEN** the runtime SHALL NOT substitute a country list, application-specific name or environment default
- **AND** v1 SHALL NOT accept embedded URL userinfo, fragments or URL authentication fields

### Requirement: Network group dependency management
The system SHALL support `networkgroup` aliases that compose address-compatible aliases, validate resolvable dependencies before writes and preserve external ownership.

#### Scenario: Present aliases are declared out of dependency order
- **WHEN** a group references other aliases created in the same invocation
- **THEN** the workflow SHALL apply present dependencies before dependent groups regardless of input order
- **AND** it SHALL suppress per-batch reload and reload alias configuration once after successful actual changes, with no reload for an ordinary no-op unless the caller explicitly requests activation recovery

#### Scenario: Group references an externally owned alias
- **WHEN** a surviving present group has a syntactically valid reference that cannot be resolved from local desired state
- **THEN** the workflow SHALL resolve its existence, compatible type and reachable group dependencies through read-only preflight before any mutation
- **AND** missing, incompatible, cyclic or unreadable references SHALL fail without mutation
- **AND** the external alias SHALL NOT become owned or rewritten by the group declaration

#### Scenario: Group or member is removed
- **WHEN** explicitly absent aliases have dependents
- **THEN** the workflow SHALL evaluate surviving managed references after applying desired updates and order removals using existing live dependencies, dependents first
- **AND** a group and its members MAY be removed together without validating obsolete absent-group content as surviving references
- **AND** external consumers SHALL remain protected by the appliance's final in-use deletion check; refusal SHALL fail without bypass
- **AND** an already absent target SHALL be an idempotent no-op
- **AND** the workflow SHALL NOT delete external consumers or unlisted aliases to satisfy a removal

#### Scenario: A later write fails
- **WHEN** an alias batch partially succeeds before another batch fails
- **THEN** the workflow SHALL fail and identify that partial configuration changes may exist
- **AND** it SHALL NOT claim transactionality, rollback or successful activation

### Requirement: Application-neutral gateway and rule composition
Alias extensions SHALL compose with the repaired gateway and API-backed filter-rule capabilities while preserving resource field shapes, ownership boundaries and application-neutral behavior.

#### Scenario: Caller uses aliases in PBR
- **WHEN** a caller supplies source/destination alias references, inversion, sequence, optional gateway and log fields
- **THEN** the existing gateway and filter-rule entrypoints SHALL retain their documented semantics
- **AND** non-default gateway ownership, scope/slug rule identity and unlisted-object preservation SHALL remain in force
- **AND** no routing preference, direct-access exception or failure policy SHALL be inferred from names or application identity

### Requirement: Effective alias graph and type continuity
Before writes, the alias workflow SHALL combine desired present definitions and removals with externally owned live definitions to validate surviving managed dependencies without silently replacing types.

#### Scenario: Desired update releases an old dependency
- **WHEN** a surviving group replaces an old member with a new member and the old member is marked absent
- **THEN** the new dependency SHALL be created first, the group SHALL be updated next, and the old member SHALL be removed last
- **AND** dependency validation SHALL use the desired group definition rather than reject its superseded live reference

#### Scenario: Existing alias name changes type
- **WHEN** a present declaration changes the type of an existing alias
- **THEN** preflight SHALL fail before writes and require an explicit caller migration
- **AND** it SHALL NOT silently delete and recreate that alias
