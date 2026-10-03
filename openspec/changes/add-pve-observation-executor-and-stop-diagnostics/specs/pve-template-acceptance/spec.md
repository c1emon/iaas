## ADDED Requirements

### Requirement: Clone ownership waits without premature registration
Acceptance plan SHALL generate a fresh one-use noncredential correlation marker and bind it to the preview consumed by admission. Start SHALL persist that marker with original clone intent and target/source bindings before dispatch and carry it only in the original native clone description, without a separate configuration write. It SHALL record the returned UPID before ownership checking and incrementally retain safe candidate identity/configuration/storage evidence. After confirmed clone success it SHALL independently read and retain a marker-matching candidate UUID and complete slot-to-volume configuration snapshot before pool/storage-content registration gates, using bounded observation for synchronized views. Snapshot completeness SHALL require the frozen source's expected clone disk slots, target storage and absence of source-volume reuse. Candidate resources SHALL remain ownership unknown until all registration predicates, including pool and matching storage volid/vmid facts, pass. Explicit marker, identity or ownership conflicts SHALL fail immediately and SHALL NOT authorize cleanup.

#### Scenario: Pool and disk rows synchronize after clone success
- **WHEN** the first post-clone view temporarily lacks pool membership or storage rows under a declared pending condition
- **THEN** acceptance SHALL continue observation of the same target and task within the original window
- **AND** it SHALL register ownership only after the complete independent checks pass, with exactly one clone dispatched

#### Scenario: Ownership confirmation stops before journal registration
- **WHEN** clone completed but ownership checking fails or expires before the full resource record is registered
- **THEN** original task association, candidate observations and the failed check SHALL remain available for constrained recovery assessment
- **AND** candidate existence SHALL NOT permit automatic adoption, stop or deletion

#### Scenario: Correlation is supplied with the original clone
- **WHEN** current acceptance is admitted and its free target and source bindings are established
- **THEN** the single clone dispatch SHALL carry the preview-bound marker, with its request fields and returned UPID retained in protected original evidence
- **AND** no later write SHALL add or replace a marker to manufacture historical association

#### Scenario: Candidate configuration is incomplete
- **WHEN** the post-task view lacks required UUID or disk slots
- **THEN** partial safe fields SHALL be retained as incomplete while bounded observation continues
- **AND** expiry before a complete candidate snapshot SHALL leave pre-registration cleanup ineligible rather than fill original identities from later current state

### Requirement: Configuration and guest checks observe convergence safely
Acceptance SHALL wait for requested configuration and disk capacity after the original modify/resize operation, for QGA/cloud-init readiness, and for required partition/filesystem growth, identity, addresses, routes and DNS within the original work budget. Only declared initialization states SHALL be pending; explicit cloud-init failure, illegal configuration or identity conflicts SHALL stop immediately. Guest exec-status query retries SHALL retain the same PID. A subsequent fixed read-only guest sample SHALL be dispatched only after the preceding sample is confirmed exited.

#### Scenario: Disk and guest growth are not immediately visible
- **WHEN** the resize task succeeded but configuration capacity or the initializing guest growth facts are not yet ready
- **THEN** acceptance SHALL perform bounded observation and pass only after required disk, root partition and filesystem capacities are established
- **AND** it SHALL NOT repeat resize or remediate the guest

#### Scenario: Guest status read temporarily fails
- **WHEN** a fixed read-only program returned a PID and exec-status suffers an allowed temporary error
- **THEN** observation SHALL retry only that PID under the original deadline
- **AND** an unknown exec response or PID SHALL prevent another exec dispatch

#### Scenario: Initialization completes with wrong required facts
- **WHEN** cloud-init explicitly fails or a complete authoritative guest observation establishes a non-pending wrong identity or invalid network configuration
- **THEN** the affected check SHALL fail with necessary facts and SHALL NOT be delayed as a generic transient error

### Requirement: Acceptance cleanup waits for resource disappearance
After a known successful delete task, acceptance SHALL use bounded read-only checks for original VM and exact owned volume absence, including successful queries still showing stale original objects. Permitted query retries SHALL share the original cleanup deadline. Native task failure SHALL stop dependent deletion processing without write replay; uncertain activity, ownership, visibility or disappearance SHALL remain explicit.

#### Scenario: VM or storage inventory lags deletion
- **WHEN** delete completed OK but an initial successful inventory still lists the original VM or owned volumes
- **THEN** cleanup SHALL wait within the original window for complete absence evidence without issuing delete again

#### Scenario: Delete fails or disappearance cannot be confirmed
- **WHEN** delete returns an explicit non-OK task outcome or observation reaches cutoff without complete absence evidence
- **THEN** results SHALL preserve the failed task or unknown disappearance separately with exact known residue identities and last observations
- **AND** neither case SHALL trigger repeated facility deletion

## MODIFIED Requirements

### Requirement: Absolute deadlines are execution-bound
Current versioned acceptance request/result SHALL carry frozen `deadlines.work_deadline_at` and `deadlines.cleanup_deadline_at` in valid UTC `YYYY-MM-DDTHH:mm:ssZ` format with work not later than cleanup. The runtime SHALL bind both values into the canonical request and preview digests, matching operation-specific execution admission deadlines, execution identity and persisted request/admission/journal/result. Relative timeouts SHALL only impose stricter local limits.

#### Scenario: Deadline binding or format is invalid
- **WHEN** a required cutoff is missing, malformed, calendar-invalid, incorrectly ordered or conflicts with admission or original materials
- **THEN** the runtime SHALL refuse dependent facility mutation without deriving a replacement window

#### Scenario: Start has arrived too late
- **WHEN** start reaches admission at or after either frozen cutoff
- **THEN** it SHALL return a non-success deadline rejection with zero facility writes and preserve the execution association and rejection reason
- **AND** it SHALL record admission/rejected and facility_writes none separately from resource state; unchecked existence SHALL remain unknown and overall SHALL follow unknown-first aggregation without invented inventory
