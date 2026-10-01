## ADDED Requirements

### Requirement: Standalone cleanup uses a frozen authorized window
Snippet cleanup request/result v2 SHALL carry mandatory work and cleanup deadlines using valid UTC `YYYY-MM-DDTHH:mm:ssZ` with work not later than cleanup. Both SHALL be bound to request digest, operation-specific execution admission deadlines, execution identity and durable original materials. Start and initial evidence/scope admission SHALL complete within work cutoff; facility cleanup SHALL occur only within cleanup cutoff after valid work admission. Relative timeouts SHALL only tighten these limits.

#### Scenario: Cleanup admission is late or conflicts
- **WHEN** start is at or after either cutoff, initial admission cannot finish within work cutoff, or deadline materials conflict
- **THEN** cleanup SHALL refuse new deletion and report the deadline or binding reason without obtaining admission through the later cleanup window

#### Scenario: Expired admission leaves resource existence unknown
- **WHEN** a deadline rejects admission before any facility write and file existence was not inspected
- **THEN** result/journal SHALL record admission/rejected and facility_writes none, return a nonzero exit code and retain unknown file existence with unknown-first overall aggregation
- **AND** consumers SHALL NOT interpret unknown resource state as a possible write by this execution or fabricate complete inventory

#### Scenario: Work clock moves backward before cleanup
- **WHEN** start freezes both monotonic upper bounds from the same UTC/monotonic reference and UTC subsequently moves backward during admission
- **THEN** entry into cleanup SHALL retain the original cleanup upper bound and any tightening rather than recalculate a larger budget

#### Scenario: Work window ends after valid admission
- **WHEN** initial evidence and scope admission succeeded before work cutoff and cleanup window remains valid
- **THEN** cleanup MAY continue exact-list deletion within cleanup cutoff subject to renewed per-item ownership, digest, reference and serialization checks
- **AND** no new objects or VM/state mutations SHALL be introduced

### Requirement: Deletion is checked at the native write boundary
The runtime SHALL recheck cleanup cutoff before every helper deletion dispatch and bound each call, retry and wait by remaining absolute and non-extending monotonic budgets and relative limits. The restricted helper SHALL accept the frozen cutoff via deadline protocol v2 and independently check it after lock/reference/content validation immediately before unlink. A local SSH timeout SHALL NOT establish remote termination.

#### Scenario: Delete mode omits the cutoff
- **WHEN** the explicit snippet deletion mode receives no valid cleanup cutoff
- **THEN** the helper SHALL reject mutation rather than treat absence of the field as permission to skip deadline checks

#### Scenario: Expiry during a batch
- **WHEN** the cleanup cutoff is reached after some files completed but before another dispatch or unlink
- **THEN** no later deletion SHALL start; completed per-file facts SHALL remain recorded and remaining or unknown resources SHALL remain explicit
- **AND** the batch SHALL be non-success with cleanup deadline and residual reasons

#### Scenario: Delayed helper or old protocol
- **WHEN** a helper arrives late, expires while waiting for a lock or cannot enforce the deadline protocol
- **THEN** it SHALL NOT perform deletion after cutoff or downgrade to unchecked deletion

#### Scenario: Delete response is lost
- **WHEN** a dispatched delete times out or loses its response
- **THEN** the result SHALL preserve unknown activity/outcome and original ownership evidence without declaring cancellation or assuming already_absent

### Requirement: New cleanup authority does not extend old execution
A subsequent cleanup SHALL require a new execution ID, currently valid explicit deadline-bound admission and request, retaining the previous execution/material associations and unchanged full original ownership list. Retry comparison SHALL allow only deadlines, relative timeout and retry association changes. Old request/journal/result windows SHALL remain immutable; original activity must be established as stopped before new mutation.

#### Scenario: Retry with newly approved limited authority
- **WHEN** new valid admission and deadlines bind the unchanged original full list and previous execution is proven inactive
- **THEN** a new execution MAY repeat the safety checks and clean remaining exact items without extending or rewriting the old execution or acceptance result

#### Scenario: Reuse expired authority or observe
- **WHEN** the caller reuses expired start authority or observes an existing execution after cutoff
- **THEN** expired start SHALL refuse writes and observe SHALL remain read-only without recomputing budgets or replaying cleanup
- **AND** a new output path, Runner or copied admission SHALL NOT renew authorization
