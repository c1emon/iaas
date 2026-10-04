# bounded-observation-executor Specification

## Purpose
Define shared finite read-only observation semantics for task completion, target-state convergence and transient query retry, preserving fixed associations, original deadlines and truthful stop evidence without replaying mutations.

## Requirements

### Requirement: Observation never dispatches or replays mutations
The system SHALL provide a shared observation executor operating on admitted read-only probes and frozen task, process or resource associations. Mutation dispatch SHALL remain outside the executor and occur at most once per original operation except the separately specified acceptance-cleanup storage-plugin DELETE fallback, which SHALL remain outside the observer. HTTP method alone SHALL NOT establish read-only semantics. Unknown write acceptance or missing association SHALL NOT authorize redispatch, resource adoption or inferred historical success.

#### Scenario: Observe a clone after a temporary query failure
- **WHEN** a dispatched clone returned a bound UPID and an admitted task-status query temporarily fails
- **THEN** permitted retries SHALL query only that UPID without another clone request
- **AND** later target-state observation SHALL retain the original execution and resource association

#### Scenario: Mutation response has no usable association
- **WHEN** a write may have been accepted but no reliable UPID or PID was received
- **THEN** observation SHALL retain unknown outcome and refuse automatic replay or association by current resource existence alone

### Requirement: Classifications distinguish pending failure and uncertainty
Each probe SHALL use an explicit policy distinguishing ready, pending, known failed and unknown observations. Only declared temporary read failures or declared not-yet-ready states SHALL permit another observation. Permission denial, TLS trust failure, invalid input or response, ownership conflict and explicit native task failure SHALL terminate the affected check immediately. A stopped task with missing terminal outcome SHALL NOT be reported as successful or as an explicit non-OK task failure.

#### Scenario: Missing state later converges
- **WHEN** a successful query temporarily lacks a required synchronized field under a declared pending condition
- **THEN** the executor SHALL continue bounded observation and pass only after the required facts are independently established

#### Scenario: Explicit failure or ownership conflict
- **WHEN** a task reports a non-OK exitstatus such as unexpected status, or the probe establishes a conflicting owner
- **THEN** the check SHALL fail immediately with the necessary observation retained
- **AND** no observer retry SHALL hide that failure or repeat the facility operation; only the separately specified acceptance-cleanup storage-plugin DELETE fallback may initiate a new bounded attempt outside the observer while retaining the failed check

#### Scenario: Failure is not safely classified as transient
- **WHEN** a query has an unclassified exception, malformed data, denied permission or failed TLS trust
- **THEN** the executor SHALL stop with failed or unknown as justified, rather than treating all query exceptions as retryable

### Requirement: All observation shares non-extending execution bounds
Every request, response-processing step, polling pause and permitted retry SHALL consume the supplied applicable absolute and non-extending monotonic budget. Operations with work and cleanup windows SHALL freeze both upper bounds at one start reference; independent read-only verification SHALL freeze its own observation bound once without renewing any original mutation authority. Stage-local caps SHALL only tighten the budget and SHALL NOT reset on probe attempts or phase transitions. After cutoff the executor SHALL issue no new online probe and SHALL retain unresolved pending state as unknown with each affected check's last necessary observation and applicable cutoff.

#### Scenario: Retry approaches the original cutoff
- **WHEN** repeated pending or temporary-error probes consume the original window
- **THEN** the next request and pause SHALL use only remaining time and SHALL NOT receive a fresh full timeout
- **AND** unresolved completion, activity or existence SHALL remain unknown at expiry

#### Scenario: Clock moves backward before cleanup
- **WHEN** UTC moves backward after work and cleanup bounds were frozen
- **THEN** cleanup and later probes SHALL retain their original monotonic upper bounds and any prior tightening

### Requirement: Evidence is captured before classification stops execution
The executor SHALL retain bounded, allowlisted decision evidence before a check raises or stops: execution association, phase/check, query time, attempt, fixed task/resource identity, necessary expected and actual fields, controlled error category and reason. Evidence SHALL be grouped by fixed phase/check/resource-or-task association, with terminal decision evidence preserved for every completed or failed check. Later cleanup, source verification or independent observations SHALL NOT overwrite earlier failure evidence. Unobserved or incomplete data SHALL remain distinct from empty successful inventories. Each group's last necessary observations and material changes SHALL be retained without requiring all polling responses or sensitive payloads.

#### Scenario: Volume ownership check fails
- **WHEN** observed storage rows conflict with the expected clone ownership
- **THEN** evidence SHALL preserve the relevant volid/vmid and capacity fields with expected ownership, phase, query time and reason even before resource registration
- **AND** raw response payloads and credentials SHALL remain excluded from consumable diagnostics

#### Scenario: Final query fails after an earlier useful observation
- **WHEN** the final allowed query fails
- **THEN** the earlier safe observation and its timestamp SHALL remain available alongside the new query error
- **AND** that earlier observation SHALL NOT be presented as a newly confirmed current state

#### Scenario: Cleanup follows a clone ownership failure
- **WHEN** claim failed with necessary observations for two volumes and later cleanup or source checks continue
- **THEN** the original check's volid/vmid, expected ownership, phase, query time and reason SHALL remain consumable alongside subsequent independently grouped observations
- **AND** the final diagnostic SHALL NOT replace them with a global last observation
