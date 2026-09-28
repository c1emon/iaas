## ADDED Requirements

### Requirement: Bounded PVE acceptance and snippet cleanup entrypoints
The shared launcher SHALL expose fixed-request template acceptance and standalone VM snippet cleanup with current versioned contracts, machine-readable capabilities, common consumer fixtures and truthful effect declarations.

#### Scenario: Discover or invoke the new operations
- **WHEN** a caller uses pve-template accept or pve snippet-cleanup
- **THEN** the launcher SHALL require explicit start or observe mode, validate the corresponding request/admission or original execution materials, advertise start as infrastructure-writing without state writes and observe as read-only, and dispatch through the existing runtime
- **AND** missing or unsupported capability versions SHALL be rejected without adapting historical records or invoking prerequisite preparation implicitly

#### Scenario: Map original execution and cleanup evidence across Runners
- **WHEN** observe or a new cleanup execution consumes prior protected materials
- **THEN** files.original_execution_dir and files.cleanup_evidence_dir SHALL be explicitly mapped read-only as applicable, with confined relative references and identity/digest validation
- **AND** observe SHALL require no new execution admission, SHALL write only to its new collection output and SHALL NOT mutate PVE or overwrite original evidence
- **AND** missing core material SHALL prevent mutation rather than cause start fallback or reconstruction of historical success

#### Scenario: Preserve isolated trust and credentials
- **WHEN** the launcher transports acceptance or cleanup materials through local Docker or DinD
- **THEN** it SHALL preserve current TLS/private-CA validation, strict SSH host verification, protected file mapping and operation-scoped credentials
- **AND** acceptance SHALL NOT receive artifact-download credentials, snippet cleanup SHALL NOT receive state-backend credentials, and public output SHALL exclude raw guest, cloud-init and credential material

#### Scenario: Return incomplete or unknown execution
- **WHEN** mutation or result collection is incomplete
- **THEN** the launcher SHALL retain protected original evidence, expose failed/unknown outcomes and avoid a success exit for incomplete acceptance/cleanup
- **AND** read-only observation SHALL NOT replay an execution or manufacture historical success

#### Scenario: Deliver software capability without site qualification
- **WHEN** implementation is released
- **THEN** IaaS SHALL ship current request/result schemas, shared positive/negative examples, invocation/version notes and minimal helper installation/permissions
- **AND** software fixture results SHALL NOT be described as real PVE qualification; real VM creation/deletion SHALL require a separately bounded caller authorization
