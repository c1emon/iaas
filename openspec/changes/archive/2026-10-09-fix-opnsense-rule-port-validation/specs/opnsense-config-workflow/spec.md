## ADDED Requirements

### Requirement: Sanitized API save validation evidence
The workflow SHALL retain bounded sanitized API validation field and reason details in protected stage facts and workflow result/recovery files. It SHALL preserve credential/raw-configuration protection and stop activation and later stages after a failed save, without retry or rollback.

#### Scenario: Provider rejects save with validation details
- **WHEN** the fixed provider reports a validation map, including a failed loop item
- **THEN** the workflow SHALL retain known field leaves and exact static model reasons without response data, values, UUIDs, credentials or invocation
- **AND** unknown fields/reasons SHALL be explicitly redacted rather than copied verbatim
- **AND** the result SHALL preserve partial-save uncertainty and require reconciliation before a fresh plan and approval
