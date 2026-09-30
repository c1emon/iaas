## ADDED Requirements

### Requirement: Launcher exposes the absolute deadline contract
Capabilities SHALL advertise v2 acceptance/cleanup request/result contracts and per-operation absolute_deadlines support. The launcher SHALL require compatible capability declarations and transmit frozen request/admission and protected original materials unchanged through local and DinD execution. Capability checks SHALL NOT substitute for internal native deadline enforcement.

#### Scenario: Caller selects an incompatible runtime
- **WHEN** a selected runtime lacks the current contracts or absolute deadline support
- **THEN** the launcher SHALL reject invocation without silently choosing another image, defaulting deadlines or converting relative timeouts to approval windows

#### Scenario: Delayed transport and expired observation
- **WHEN** transfer or container startup delays execution, or observe reads expired original materials
- **THEN** transmitted deadlines SHALL remain unchanged, start SHALL rely on native remaining-window checks, and observe SHALL remain read-only without renewed budgets

### Requirement: Deadline implementation has fixed consumable delivery
After implementation and scoped validation, IaaS SHALL publish a new immutable runtime release and matching launcher assets through the existing release process, documenting runtime manifest/platform digests, launcher checksums, current capabilities and deadline-aware helper installation requirements. infra-ops SHALL own calculation and persistence of deadlines from lawful target start and approved policy; IaaS SHALL enforce the received frozen windows internally.

#### Scenario: Consume the released implementation
- **WHEN** infra-ops pins the documented runtime digest and checksum-verified launcher release
- **THEN** the artifacts SHALL expose and enforce the declared deadline contract without a source checkout
- **AND** release completion SHALL require actual published artifacts rather than workflow configuration or local fixture success

#### Scenario: Report validation boundaries
- **WHEN** software tests or publication complete
- **THEN** the delivery record SHALL distinguish those results from real PVE, shared environment or production qualification
