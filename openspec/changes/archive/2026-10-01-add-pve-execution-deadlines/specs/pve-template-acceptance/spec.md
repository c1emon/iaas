## ADDED Requirements

### Requirement: Absolute deadlines are execution-bound
Acceptance request/result v2 SHALL carry frozen `deadlines.work_deadline_at` and `deadlines.cleanup_deadline_at` in valid UTC `YYYY-MM-DDTHH:mm:ssZ` format with work not later than cleanup. The runtime SHALL bind both values into the canonical request digest, matching operation-specific execution admission deadlines, execution identity and persisted request/admission/journal/result. Relative timeouts SHALL only impose stricter local limits.

#### Scenario: Deadline binding or format is invalid
- **WHEN** a required cutoff is missing, malformed, calendar-invalid, incorrectly ordered or conflicts with admission or original materials
- **THEN** the runtime SHALL refuse dependent facility mutation without deriving a replacement window

#### Scenario: Start has arrived too late
- **WHEN** start reaches admission at or after either frozen cutoff
- **THEN** it SHALL return a non-success deadline rejection with zero facility writes and preserve the execution association and rejection reason
- **AND** it SHALL record admission/rejected and facility_writes none separately from resource state; unchecked existence SHALL remain unknown and overall SHALL follow unknown-first aggregation without invented inventory

### Requirement: Native acceptance enforces remaining windows
The runtime SHALL check the applicable cutoff at each stage and immediately before each new facility write, including after durable intent persistence. HTTP, guest-agent, internal retries, SSH/helper calls and polling waits SHALL be bounded by the smaller of frozen absolute remaining time, non-extending monotonic remaining budget and applicable relative limits. It SHALL NOT restart a full absolute budget on phase entry, retry or recovery.

#### Scenario: Freeze both windows at start
- **WHEN** start establishes its UTC and monotonic time reference
- **THEN** it SHALL simultaneously freeze work and cleanup monotonic upper bounds from that same reference
- **AND** later stages SHALL only tighten these bounds, never recompute a larger cleanup budget at phase entry

#### Scenario: Work stage starts late
- **WHEN** clone, temporary configuration, snippet upload, startup or guest acceptance reaches its execution check at or after work cutoff
- **THEN** it SHALL NOT start that work operation and SHALL retain failed/unattempted/unknown checks as applicable
- **AND** it MAY enter cleanup only within the frozen cleanup window, for confirmed execution-owned resources without active or uncertain conflicting mutations

#### Scenario: Cleanup reaches its cutoff
- **WHEN** cleanup reaches its frozen cutoff before another stop/delete or snippet deletion
- **THEN** it SHALL issue no new facility write or active online polling and SHALL retain completed facts, residual identities and unknown existence/activity evidence in local materials
- **AND** source recheck within the cleanup window SHALL remain read-only and SHALL NOT substitute for unfinished guest acceptance

#### Scenario: A sent operation is still unresolved
- **WHEN** a local timeout or cutoff occurs after sending a PVE task, guest execution or remote helper operation
- **THEN** the runtime SHALL preserve native identifiers and uncertain activity/outcome and SHALL NOT claim cancellation, rollback or historical deletion success
- **AND** it SHALL NOT clean resources whose ownership or conflicting activity cannot be safely established

#### Scenario: Remote upload is delayed
- **WHEN** the acceptance upload helper reaches its actual create operation after lock or verification delay
- **THEN** the helper SHALL independently check the transmitted work cutoff immediately before creation and refuse an expired write
- **AND** missing helper deadline protocol support SHALL prevent mutation

#### Scenario: Upload mode requires a deadline
- **WHEN** the runtime invokes an acceptance upload
- **THEN** it SHALL use the explicit acceptance upload mode, whose helper SHALL require a valid work cutoff even when the cutoff field is absent
- **AND** the runtime SHALL NOT fall back to ordinary upload mode; ordinary VM cloud-init upload SHALL retain its existing semantics without mandatory deadline fields

### Requirement: Deadline outcomes remain truthful on observation
Results SHALL distinguish admission deadline rejection, work deadline exhaustion, ordinary stage failure, cleanup deadline exhaustion/incompleteness and uncertain native outcomes through frozen deadlines, structured deadline_outcome and stage/item reasons. Unknown facts SHALL prevent success; successful cleanup SHALL NOT turn failed acceptance into passed.

#### Scenario: Distinguish resource uncertainty from current writes
- **WHEN** resource state is unknown but this execution is confirmed to have issued no facility write
- **THEN** journal/result SHALL independently record facility_writes none and retain unknown resource facts
- **AND** consumers SHALL NOT infer a possible write by this execution from resource uncertainty alone; facility_writes issued or unknown SHALL describe only this execution, not resource existence or previous operations

#### Scenario: Failed work is cleaned successfully
- **WHEN** work cutoff blocks required acceptance and all permitted cleanup succeeds
- **THEN** the acceptance SHALL remain non-success with the original work failure visible

#### Scenario: Observe after the approved window
- **WHEN** an already dispatched execution is observed after either cutoff
- **THEN** observe SHALL validate and read the original frozen bindings and available facts without refreshing deadlines, writing infrastructure or restarting side effects
- **AND** missing core materials SHALL remain unknown rather than authorize a fresh start

#### Scenario: Clock moves backward before cleanup
- **WHEN** UTC moves backward during work and the execution subsequently enters cleanup
- **THEN** cleanup remaining budget SHALL NOT exceed its monotonic upper bound frozen at start or any subsequent tightening
- **AND** unavailable trustworthy time SHALL refuse new writes rather than create a replacement window
