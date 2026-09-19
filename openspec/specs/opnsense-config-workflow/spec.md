# opnsense-config-workflow Specification

## Purpose
Provide a generic, explicitly scoped OPNsense configuration workflow for reading live resources, reviewing candidates, executing selected changes, verifying results and preparing bounded recovery while leaving site policy and deployment records with callers.

## Requirements

### Requirement: Generic workflow and ownership boundary
The system SHALL provide read, plan, apply and verify operations for the existing aliases, IP Alias VIPs, PBR gateways, filter rules, DNAT, one-to-one NAT and interface groups. It SHALL preserve each resource's existing schema, identity, address-family and ownership constraints. It SHALL consume standard declarations independently of their authoring tool and SHALL NOT compile site policy, infer business permissions, choose migration stages, maintain deployment baselines or interpret caller-specific ownership metadata. Unsupported resources and arbitrary API or command requests SHALL fail before writes.

#### Scenario: Caller supplies generated resources
- **WHEN** a caller supplies valid standard resources produced by an external policy generator
- **THEN** the workflow treats them equivalently to handwritten declarations without requiring the generator or its metadata in iaas
- **AND** no caller deployment pointer or previous-generation baseline is read or advanced

#### Scenario: Deferred resource requested
- **WHEN** a caller selects SNAT, DHCP, RA or another unsupported resource
- **THEN** admission rejects that operation before device mutation without extending the resource contract

### Requirement: Explicit target and resource selection
Each online workflow SHALL require exactly one explicit existing inventory target and an explicit resource-class or stable-object selection. Read SHALL select live resources from its request without requiring desired declarations or a candidate. Plan SHALL select declarations from its standard inputs; apply and verify SHALL use the candidate's fixed selection. For declaration-based selection, a class SHALL select only supplied declarations of that class and an object SHALL resolve an exact declared identity, not sequence or approximate content. Missing or ambiguous selection SHALL fail, while a declared present object absent on the appliance SHALL remain eligible for creation. Empty declaration lists SHALL be no-ops and omission SHALL preserve objects. A necessary dependency read SHALL NOT authorize a dependency write. First adoption of an existing unmanaged matching object SHALL require an explicit caller decision recorded with the reviewed difference.

#### Scenario: Read before preparing declarations
- **WHEN** a caller requests a supported resource class or exact live identity for one inventory target without supplying a candidate
- **THEN** read returns bounded live observations and their coverage without requiring or generating desired declarations
- **AND** a complete lookup of a missing exact identity reports absence without mutation

#### Scenario: Object subset selected
- **WHEN** a candidate contains multiple declarations but the request selects only two stable identities
- **THEN** only those identities are eligible for writes and other declarations remain available only as candidate context
- **AND** identities missing from the supplied declarations and duplicate live matches are rejected rather than guessed

#### Scenario: Empty execution set
- **WHEN** the explicitly selected candidate list is empty
- **THEN** no appliance object is deleted or adopted and no ordinary reload occurs

#### Scenario: Same name does not authorize adoption
- **WHEN** a selected present object matches a live object outside the caller's declared management scope
- **THEN** plan identifies the adoption decision and apply refuses it unless the caller explicitly included that exact object in the reviewed adoption selection

### Requirement: Bounded configuration reads and semantic differences
Read and plan SHALL retrieve only selected configuration and necessary dependency or reverse-reference information using bounded read-only operations. Results SHALL distinguish complete, unsupported, incomplete and failed observations. Plan SHALL distinguish create, update, explicit delete, unchanged and unknown using managed configuration semantics, excluding non-configuration counters and timestamps. Missing objects SHALL be concluded only from a complete relevant lookup; unknown or truncated results SHALL NOT be interpreted as absent or unchanged. These operations SHALL NOT save, activate, refresh Alias contents or clear connection state.

#### Scenario: Incomplete lookup
- **WHEN** a lookup is truncated, times out, omits a required field or has ambiguous identity matches
- **THEN** the affected difference is unknown and apply cannot use it as an admitted mutation
- **AND** the result identifies the bounded coverage without exposing raw sensitive responses

#### Scenario: Effective field changes
- **WHEN** a selected rule changes sequence, IP family, ports or gateway while counters also change
- **THEN** the configuration difference shows the effective field changes and excludes counters

#### Scenario: Dynamic Alias observation
- **WHEN** a DNS or URL-table Alias has changing resolved members
- **THEN** declared configuration comparison and active membership observations remain separate
- **AND** observed entries alone do not prove periodic refresh success

### Requirement: Reviewed candidate remains the execution input
Plan SHALL produce a self-contained candidate containing resolved standard declarations, selected identities, fixed execution stages, relevant live observations, target connection identity and runtime identity. Apply SHALL consume only that explicit reviewed candidate and verify its caller-supplied reviewed digest, target, runtime digest, platform and format compatibility before writes. It SHALL NOT recompile policy, load replacement desired inputs or silently replan. Available source revision and dirty state SHALL be recorded honestly; unavailable provenance SHALL remain unavailable. Credentials SHALL be injected separately and SHALL NOT be saved in the candidate.

#### Scenario: Source changes after planning
- **WHEN** the caller edits original policy or standard resource inputs after reviewing a candidate
- **THEN** applying the unchanged candidate uses its captured declarations and selection
- **AND** it does not run the generator or substitute current inputs

#### Scenario: Candidate or target changes
- **WHEN** candidate bytes, resolved API endpoint, target TLS settings, runtime digest or platform differ from the reviewed binding
- **THEN** apply fails before device writes and requires a newly reviewed compatible candidate

### Requirement: Effective-state reference admission and ordering
The complete candidate SHALL receive static declaration validation, but execution admission SHALL use selected changes overlaid on the necessary live state of unselected objects. Supported forward and reverse references SHALL be checked before the first write and at relevant stage boundaries. The system SHALL order only explicitly selected writes to establish new references, switch references and retire old objects, preserving required dependencies at every actual activation stage. Missing dependent selections, cycles or unsupported safe ordering SHALL reject the execution with guidance, not expand its write scope. Site migration sequencing SHALL remain caller-owned.

#### Scenario: Candidate reference switch is not selected
- **WHEN** the full candidate changes a rule from Alias A to B but the execution selects only deletion of A while the live rule still references A
- **THEN** admission rejects deletion before the first write and identifies the missing reference transition
- **AND** the unselected candidate rule is not treated as live or silently written

#### Scenario: Selected rename sequence
- **WHEN** the caller explicitly selects creation of a replacement Alias, all required reference switches and retirement of the old Alias
- **THEN** the workflow orders the selected stages with valid references and required activation between them
- **AND** native reference protection remains effective for remaining external references

### Requirement: Relevant drift and shared activation admission
Apply SHALL re-read affected objects and necessary references before the first write and reject relevant changes or unknown required state compared with the reviewed candidate. Shared activation effects SHALL be disclosed independently of object write selection. Detected pending changes outside the reviewed activation authorization SHALL stop execution. Where automatic detection is unavailable, the result SHALL say unknown and require an explicit caller check conclusion bound to the target, candidate and current execution before writes. This conclusion SHALL NOT override detected conflicts or be reported as device evidence. Callers SHALL serialize target writes; stage checks SHALL stop on observed external changes without claiming transaction isolation or requiring a whole-device per-object snapshot.

#### Scenario: Planned new identity becomes occupied
- **WHEN** an object expected to be absent in the candidate appears before apply
- **THEN** apply reports drift and performs no writes rather than updating the new occupant

#### Scenario: Unrelated pending change detected
- **WHEN** a shared filter reload would activate a detected pending change not covered by the reviewed authorization
- **THEN** the workflow stops even if that object was not selected for CRUD
- **AND** a caller assertion cannot bypass the detected conflict

#### Scenario: Pending state cannot be automatically determined
- **WHEN** the device interface cannot determine whether unrelated pending changes exist
- **THEN** the workflow reports the limitation and requires the current execution's explicit caller check conclusion before the first write
- **AND** the conclusion is recorded separately from automated observations and does not prove device isolation

### Requirement: Separate persistence activation and verification outcomes
Apply SHALL report persistence, activation and configuration verification separately, including failed, unconfirmed and not-attempted outcomes. Request acceptance alone SHALL NOT be reported as confirmed activation. Failed or unconfirmed activation SHALL stop stages that depend on that activation. A CRUD failure SHALL stop subsequent mutation and activation; bounded readback SHALL record what can still be confirmed. Timeout, cancellation or unavailable readback SHALL preserve unknown outcomes without automatic batch retry or rollback. Ordinary no-op execution SHALL NOT reload; activation recovery SHALL require an explicit reviewed candidate and normal admission checks.

#### Scenario: Save succeeds and activation fails
- **WHEN** the selected changes are saved but activation fails
- **THEN** the result reports saved configuration and failed activation separately, stops dependent stages and returns a failure status
- **AND** it does not report the previous saved configuration as automatically restored

#### Scenario: Endpoint only acknowledges invocation
- **WHEN** an activation endpoint returns ok without reliable evidence of underlying reload completion
- **THEN** the workflow uses a supported active check to establish the required result or records activation as unconfirmed
- **AND** reading saved configuration alone cannot establish activation

#### Scenario: Partial write with lost connectivity
- **WHEN** a write times out and bounded readback cannot reach the appliance
- **THEN** attempted work and unknown outcomes remain in the result and no later mutation or automatic retry runs

#### Scenario: Explicit no-change activation recovery
- **WHEN** a newly reviewed candidate explicitly requests activation recovery for unchanged saved configuration
- **THEN** the selected fixed target can activate only after drift and shared activation admission succeeds
- **AND** ordinary no-change candidates and read-only operations do not activate

### Requirement: Independent configuration and supported active verification
Verify and apply's post-write verification SHALL compare selected saved configuration with the candidate, including explicit absence, and perform supported resource-specific active checks with stated coverage. Unsupported active checks SHALL be recorded as unverified, not passed. A required failed or unknown check SHALL return nonzero and prevent dependent progression. Successful required checks with unsupported supplementary checks SHALL be distinguishable from fully verified completion. Verification SHALL NOT perform mutation, flush PF states or claim business connectivity acceptance.

#### Scenario: Deletion is verified
- **WHEN** the candidate explicitly deletes an object
- **THEN** verification requires a complete relevant lookup confirming absence rather than merely a successful delete response

#### Scenario: Active inspection unsupported
- **WHEN** saved configuration matches but a supplementary active inspection is not supported
- **THEN** results retain saved-configuration success and mark that active inspection unverified with its scope
- **AND** the task cannot be described as fully verified or as business acceptance

### Requirement: Before-state recovery with explicit new execution
Before the first write, the system SHALL protect recovery material for all potentially affected objects using actual pre-write configuration and original absence markers. The same self-contained material SHALL retain execution identity and record attempted stages and confirmed post-write state as execution progresses; missing or uncollected post-write evidence SHALL remain unknown. It SHALL distinguish fully expressible recovery from manual-required fields or modes. Recovery SHALL target reversal of that execution's affected configuration, not silently substitute a historical deployment baseline. It SHALL prepare a new plan using current observations and explicitly selected recovery material, then require the ordinary reviewed apply path. New objects SHALL have explicit inverse deletion. Subsequent changes, unresolved original outcomes or lossy reconstruction SHALL prevent automatic recovery selection until reconciled or routed to manual recovery. No automatic rollback, lease/state restoration or whole-device restore SHALL be claimed.

#### Scenario: Live before-state differs from old source
- **WHEN** a reviewed update overwrites a live managed value that differs from an older source declaration
- **THEN** recovery material retains the actual live before-state rather than that older declaration

#### Scenario: Reverse a newly created object
- **WHEN** the caller prepares recovery for an object originally confirmed absent and subsequently created
- **THEN** the recovery candidate contains its explicit deletion, subject to current reference and drift admission

#### Scenario: Recovery cannot be expressed safely
- **WHEN** unsupported native fields or subsequent edits prevent a safe inverse declaration
- **THEN** the material identifies the manual-required or unresolved scope and does not silently discard fields or overwrite later changes

### Requirement: Private results and caller-owned deployment records
The system SHALL return versioned generic results containing target, candidate and runtime identity, selected resources, attempted stages, confirmed before/after state, persistence/activation/verification outcomes, unresolved scope and recovery locations. Sensitive configuration, raw API responses and subprocess output SHALL be protected using the existing task-output contract. Output preparation failure SHALL prevent writes; failed collection SHALL preserve the only recovery copy. Results SHALL enable caller reconciliation without interpreting or advancing caller deployment baselines, policy ownership metadata or business acceptance.

#### Scenario: Partial result consumed by a caller
- **WHEN** only part of the selected execution is confirmed successful
- **THEN** the result identifies that resource scope and all failed or unknown stages
- **AND** iaas does not mark the whole candidate deployed or update caller previous-generation metadata

#### Scenario: Recovery collection fails
- **WHEN** private recovery material cannot be collected from task storage
- **THEN** the operation reports collection failure and retains the material at a disclosed protected location
- **AND** it does not expose raw output publicly or delete the only copy
