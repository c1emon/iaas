## ADDED Requirements

### Requirement: Explicit state initialization and continuity admission
PVE state-dependent lifecycle operations SHALL distinguish first use, existing state and explicitly reconciled empty state using caller-owned admission and actual backend observations.

#### Scenario: Observe state without initializing it
- **WHEN** read or admission observes the selected S3 state
- **THEN** it SHALL use a read-only object request with the exact supported endpoint, bucket, workspace-derived key, credentials and transport settings
- **AND** it SHALL NOT invoke native workspace or state-manager paths that can initialize an absent state, or issue state/lock writes during observation
- **AND** only a confirmed missing object SHALL count as absent; access denial, missing bucket, transport failure, undecodable content and unsupported application-layer encryption SHALL block admission without empty-state fallback

#### Scenario: Initialize a new execution unit
- **WHEN** the caller explicitly admits first use of a root/backend/workspace and state is confirmed absent or empty
- **THEN** the runtime SHALL also require absence of conflicts for objects the plan will create
- **AND** it SHALL NOT require proof that unrelated cluster resources are absent

#### Scenario: First-use planning establishes an empty native state
- **WHEN** explicitly authorized native planning initializes empty state after a confirmed first-use observation
- **THEN** retained plan materials SHALL associate the before/after observations and available native identity with the same root/backend/workspace
- **AND** apply SHALL compare its current caller admission and actual observation with that recorded continuity rather than requiring identical admission labels or absent/present status
- **AND** a historical first-use declaration SHALL NOT authorize recreation after an established state disappears

#### Scenario: Existing state is missing or unreadable
- **WHEN** an existing execution unit's state disappears, cannot be read or has a conflicting native identity
- **THEN** planning/application SHALL fail without treating the environment as new
- **AND** ambiguous backend failures SHALL remain unknown rather than absent

#### Scenario: Reconciled empty environment
- **WHEN** the caller supplies an explicit empty-state reconciliation association
- **THEN** actual emptiness and available native identity SHALL match that association
- **AND** neither failed reads nor a new local working directory SHALL substitute for reconciliation evidence

#### Scenario: Competing state changes after observation
- **WHEN** state changes between preflight and native apply
- **THEN** native locking and stale-plan checks SHALL remain authoritative
- **AND** preliminary lineage/serial observations SHALL NOT authorize lock bypass or automatic retry

### Requirement: Execution-time PVE credentials stay separate from fixed inputs
The runtime SHALL support noninteractive operation-specific PVE API, SSH and state credentials through explicit protected channels while preserving immutable plan configuration.

#### Scenario: Provider and helper need SSH
- **WHEN** the selected supported operation requires both provider SSH and node helper SSH
- **THEN** explicit protected credentials and host identity checks SHALL be usable by both within local Docker and DinD
- **AND** host-agent availability or a developer login SHALL NOT be assumed
- **AND** unrelated credentials and secret-provider bootstrap tokens SHALL NOT enter the runtime

#### Scenario: Provider SSH requires trusted deterministic targets
- **WHEN** a supported operation enables provider SSH
- **THEN** all possible provider SSH node addresses and ports SHALL be explicit and bound to the reviewed inputs, with usable trusted known_hosts entries verified before provider execution
- **AND** first planning SHALL derive those targets from supported static root declarations and read-only state before invoking the provider, then cross-check the produced plan; apply SHALL revalidate trust for the retained target set
- **AND** missing trust, conflicting keys or unresolved dynamic destinations SHALL reject the operation without trust-on-first-use fallback
- **AND** runtime checks SHALL use the provider's actual SSH destination and trust-file behavior rather than assume that host OpenSSH configuration applies
- **AND** operations not requiring provider SSH SHALL NOT be required to supply provider SSH credentials or node maps

#### Scenario: Guest credentials are not needed during apply
- **WHEN** apply consumes previously rendered cloud-init companions
- **THEN** it SHALL NOT require guest password variables or generate new password hashes
- **AND** private companion sensitivity SHALL remain enforced

#### Scenario: Document permission and recovery boundaries
- **WHEN** PVE lifecycle capability is delivered
- **THEN** documentation SHALL state supported API/SSH permissions, helper installation requirements, protected-file aliases and state recovery layout
- **AND** it SHALL distinguish software validation from caller-authorized device installation, state migration and real-environment acceptance
