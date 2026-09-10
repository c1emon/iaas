## MODIFIED Requirements

### Requirement: Filter rule apply after successful changes
The system SHALL activate the fixed OPNsense rule target after successful declared changes and support an explicit activation-recovery retry independent of CRUD change detection.

#### Scenario: Filter rule apply changes OPNsense state
- **WHEN** declared create, update or removal operations complete successfully with actual changes
- **THEN** the workflow SHALL reload the rule target once and report whether activation succeeded

#### Scenario: Filter rule apply makes no changes
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

### Requirement: Inversion-aware destination safety
Filter-rule safety checks SHALL evaluate destination inversion consistently in Python admission and Ansible before writes while retaining explicit ownership and management-access protections.

#### Scenario: Caller declares an inverted destination
- **WHEN** an otherwise valid deny rule targets the inverse of its own interface network
- **THEN** the workflow SHALL NOT classify that rule as denying the uninverted interface network solely from a literal name intersection
- **AND** it SHALL preserve the caller's explicit inversion without inventing routing policy

#### Scenario: A non-inverted unsafe rule is supplied
- **WHEN** a rule violates the retained management-access protection under its actual match semantics
- **THEN** validation SHALL still reject it before writes
