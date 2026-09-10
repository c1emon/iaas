## MODIFIED Requirements

### Requirement: VIP reload after successful changes
The system SHALL activate the fixed OPNsense interface_vip target after successful declared changes and support an explicit activation-recovery retry independent of CRUD change detection.

#### Scenario: VIP apply changes OPNsense state
- **WHEN** declared create, update or removal operations complete successfully with actual changes
- **THEN** the workflow SHALL reload the interface_vip target once and report whether activation succeeded

#### Scenario: VIP apply makes no changes
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
