## ADDED Requirements

### Requirement: Plan-bound PVE verification observes target convergence
Native PVE deployment verification SHALL apply shared bounded observation to saved-plan expectations for clone/create ownership and placement, configuration/disk capacity, expected power state and deleted original-object disappearance where synchronization can be pending. Post-apply verification SHALL freeze one finite observation window at verification-group entry; independent verify SHALL freeze its own window at invocation. Each SHALL use an existing applicable finite timeout or the current internal default of 120 seconds, sharing the cutoff across all selected objects, probes and retries. Any already bound applicable execution cutoff SHALL only tighten that window without being refreshed. Actual window source/start/cutoff SHALL be retained in results. This SHALL NOT introduce required apply-admission deadline fields, new mandatory independent-verify deadline inputs or a facility admission rejection solely for their absence. Both SHALL preserve determinate native-output/state associations and fixed resource identities. Neither SHALL retry provider apply, substitute current declarations for original expectations, renew original write authority or infer action completion from matching current state. Unknown expected identity and explicit ownership/configuration conflicts SHALL stop the affected check.

#### Scenario: Apply finished before the target view synchronized
- **WHEN** determinate native output and original saved-plan bindings establish the selected object and its pending expected configuration
- **THEN** post-apply verification SHALL observe only that bound object under the once-frozen verification-group budget until convergence or a truthful stop
- **AND** provider apply SHALL NOT be invoked again

#### Scenario: Replacement or expectation cannot be proven
- **WHEN** current VMID exists but required new identity/output association is missing or conflicts
- **THEN** verification SHALL remain failed/unknown as justified rather than adopting the object or declaring the original action successful

#### Scenario: Independent verify follows a completed original window
- **WHEN** the original observation window has ended and independent verify has complete original plan/output/identity evidence
- **THEN** it SHALL observe current facts under its own bounded query window without mandatory new deadline input, renewed mutation authority or modified original results
- **AND** current configuration convergence SHALL NOT establish historical apply success

#### Scenario: No explicit verification deadline is supplied
- **WHEN** an otherwise valid apply or independent verify has no separately supplied observation deadline
- **THEN** its verification entry SHALL freeze the existing applicable finite timeout or the 120-second default rather than reject apply or perform unbounded polling
- **AND** probes for subsequent objects or transient failures SHALL retain that same cutoff

#### Scenario: An existing execution window is tighter
- **WHEN** verification is enclosed by an already bound execution deadline earlier than its local observation cutoff
- **THEN** every probe SHALL use the tighter existing bound without extending it
- **AND** expiry SHALL stop verification with unknown pending facts while preserving native execution/state/collection facts without cancelling or replaying provider apply

### Requirement: Native stop diagnostics are directly consumable
Affected native lifecycle results and consumable CLI summaries SHALL expose versioned structured stop diagnostics: completed stages/substages, stopped or failed check and reason, write-dispatch facts, associated task/PID activity with query time, resource ownership and existence separately, residual inventory completeness, per-phase/check/resource necessary safe decision evidence and recovery support/eligibility with blockers or required evidence categories. Necessary terminal evidence for every completed or failed check SHALL survive later cleanup/source observations; a global last-observation slot SHALL NOT replace it. The caller SHALL NOT need to parse private logs to obtain these facts. Unknown, not observed and known failed SHALL remain distinct; only an explicit safe field allowlist SHALL be public.

#### Scenario: Failed task and unknown residue coexist
- **WHEN** a native deletion task explicitly failed but storage visibility or current activity is incomplete
- **THEN** diagnosis SHALL report the failed task/check, completed earlier stages, original UPID, and unknown residual/activity facts independently
- **AND** overall unknown SHALL NOT erase the known task failure or imply another write was dispatched

#### Scenario: Unregistered clone resources remain
- **WHEN** clone succeeded but full ownership registration did not complete
- **THEN** diagnosis SHALL identify candidates as ownership unknown, preserve necessary observed volid/vmid/UUID/pool evidence and disclose whether bounded recovery is supported and currently eligible or needs evidence
- **AND** it SHALL NOT present partial candidates as a complete owned cleanup list

#### Scenario: Collection is interrupted
- **WHEN** no final result is available but bound journal evidence remains
- **THEN** read/observe SHALL expose only the available completed/failed facts, unknown completion or activity and incomplete collection
- **AND** it SHALL neither synthesize original success nor renew execution authority

#### Scenario: Sensitive query or exception material exists
- **WHEN** a failed check involved credentials, a private artifact URL or cloud-init content
- **THEN** consumable diagnostics SHALL expose only controlled identities, required comparison facts, statuses, timestamps and reason codes
- **AND** raw responses, sensitive values and arbitrary exception strings SHALL remain excluded

#### Scenario: Later observations follow failed claim
- **WHEN** claim recorded two relevant volid/vmid rows before failing and cleanup/source checks subsequently produced other observations
- **THEN** native diagnostics SHALL retain the original claim's necessary expected/actual fields, query time, phase and reason alongside those later checks
- **AND** consumers SHALL NOT need private logs to reconstruct either check's terminal decision
