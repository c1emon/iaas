## ADDED Requirements

### Requirement: Current acceptance snapshot recovery
Exact recovery SHALL accept retained current v3 acceptance request/result snapshots with their original preview, admission, runtime, policy, identity and digest bindings, without rewriting original evidence or adding legacy compatibility.

#### Scenario: Clean resources after a current native deletion failure
- **WHEN** a current acceptance execution has retained ownership evidence and its native tasks are confirmed inactive
- **THEN** a newly admitted recovery MAY clean only that execution's complete original resources
- **AND** the original acceptance result SHALL remain unchanged even if recovery cleanup succeeds

#### Scenario: Refuse conflicting current snapshots
- **WHEN** the current request, journal, preview, admission, runtime, result or source bindings conflict
- **THEN** recovery SHALL reject the materials before any facility query or mutation
