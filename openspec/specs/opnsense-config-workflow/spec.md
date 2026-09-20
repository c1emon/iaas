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
Plan SHALL produce a self-contained candidate containing resolved standard declarations, selected identities, fixed execution stages, relevant live observations, target connection identity and runtime identity. Each actual stage SHALL additionally bind its save, configuration-readback and native-activation conditions, supplementary checks, finite observation policy and any content actions derived from selected configuration changes. Content actions SHALL identify selected resource identity, candidate source configuration and native processing semantics; they SHALL NOT require a separate source/cache/loading proof for dynamic content. Apply SHALL consume only that explicit reviewed candidate and verify its caller-supplied reviewed digest, target, runtime digest, platform and format compatibility before writes. It SHALL NOT recompile policy, load replacement desired inputs, silently replan, add content actions or turn an allowed cache reuse into an unreviewed refresh. Available source revision and dirty state SHALL be recorded honestly; unavailable provenance SHALL remain unavailable. Credentials SHALL be injected separately and SHALL NOT be saved in the candidate. Candidates missing the required new confirmation contract SHALL be rejected with re-planning guidance rather than implicitly upgraded during execution.

#### Scenario: Source changes after planning
- **WHEN** the caller edits original policy or standard resource inputs after reviewing a candidate
- **THEN** applying the unchanged candidate uses its captured declarations, selection and actions
- **AND** it does not run the generator or substitute current inputs

#### Scenario: Candidate or target changes
- **WHEN** candidate bytes, resolved API endpoint, target TLS settings, runtime digest or platform differ from the reviewed binding
- **THEN** apply fails before device writes and requires a newly reviewed compatible candidate

#### Scenario: Legacy candidate omits confirmation actions
- **WHEN** a candidate from the previous format lacks the new confirmation contract
- **THEN** the new apply or verify rejects it with explicit compatibility and re-planning guidance
- **AND** it does not invent completion conditions, append refresh operations or silently reinterpret the old candidate

#### Scenario: Native dynamic cache semantics are used
- **WHEN** a selected dynamic Alias is saved and activated
- **THEN** the device's native content and cache refresh semantics are used
- **AND** apply does not add source, cache-validity, download or DNS-resolution actions that were not reviewed

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
Apply SHALL re-read affected objects and necessary references before the first write and reject relevant changes or unknown required state compared with the reviewed candidate. Shared activation effects SHALL be disclosed independently of object write selection. Detected pending changes outside the reviewed activation authorization SHALL stop execution. Where automatic detection is unavailable, the result SHALL say unknown and require an explicit caller check conclusion bound to the target, candidate and current execution before writes. This conclusion SHALL NOT override detected conflicts or be reported as device evidence. Callers SHALL serialize target writes throughout saving, activation and configuration readback; relevant checks SHALL continue across stage boundaries and stop on observed external changes without claiming transaction isolation or requiring a whole-device per-object snapshot. A caller conclusion SHALL NOT substitute for activation completion evidence, and a confirmation failure SHALL NOT authorize a broader reload or new credentials.

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
- **AND** the conclusion is recorded separately from automated observations and does not prove device isolation or activation completion

#### Scenario: Conflict appears during confirmation
- **WHEN** a relevant external change or unauthorized pending change is detected after saving or during an activation wait
- **THEN** the workflow stops further mutation, retains confirmed and unknown effects and preserves recovery material
- **AND** it does not enlarge reload scope, override the conflict or claim the previous operation was cancelled on the appliance

### Requirement: Separate persistence activation and verification outcomes
Apply SHALL report persistence, native activation, saved-configuration verification, optional deep inspection and business acceptance separately, including failed, warning, unknown and not-attempted outcomes with their evidence and uncovered scope. Request acceptance alone SHALL NOT be reported as confirmed activation. Current membership equality, a nonempty table or a timestamp change SHALL NOT replace save/readback/native-activation evidence. Default completion SHALL require successful persistence, configuration readback and native activation response; known Alias/Gateway/Group deep gaps SHALL emit a fixed non-disableable stderr warning and be recorded in result without blocking continuation. A CRUD failure SHALL stop subsequent mutation and activation; bounded readback SHALL record what can still be confirmed. Timeout, cancellation or unavailable readback SHALL preserve unknown outcomes without automatic batch retry or rollback. Ordinary no-op execution SHALL NOT reload; activation recovery SHALL require an explicit reviewed candidate and normal admission checks, and SHALL NOT authorize independent forced content refresh.

#### Scenario: Save succeeds and activation fails
- **WHEN** the selected changes are saved but activation fails
- **THEN** the result reports saved configuration and failed activation separately, stops dependent stages and returns a failure status
- **AND** it does not report the previous saved configuration as automatically restored

#### Scenario: Endpoint only acknowledges invocation
- **WHEN** an activation endpoint returns ok without reliable evidence of underlying reload completion
- **THEN** the workflow records the native activation result and configuration readback separately
- **AND** any known deep evidence gap is emitted as a fixed warning and recorded in result
- **AND** reading saved configuration or matching active members alone cannot establish completion of that invocation

#### Scenario: Partial write with lost connectivity
- **WHEN** a write times out and bounded readback cannot reach the appliance
- **THEN** attempted work and unknown outcomes remain in the result and no later mutation or automatic retry runs

#### Scenario: Explicit no-change activation recovery
- **WHEN** a newly reviewed candidate explicitly requests activation recovery for unchanged saved configuration
- **THEN** the selected fixed target can activate only after drift, necessary confirmation capability and shared activation admission succeeds
- **AND** ordinary no-change candidates and read-only operations do not activate
- **AND** activation recovery does not add independent forced downloading or DNS resolution; any native content-processing effects of the fixed activation are disclosed and bound to the new candidate
- **AND** where native activation returns failure, the result retains that failure and reconciled post-state for explicit recovery planning rather than a generic re-planning loop

#### Scenario: Successful native activation leaves equal members
- **WHEN** native activation and configuration readback succeed and the resulting members equal the previous members
- **THEN** the native activation and current member observation remain separately recorded
- **AND** equality neither adds a forced content action nor changes the default result

#### Scenario: Failed native activation leaves matching old members
- **WHEN** native activation explicitly fails but the previous members still match an optional current-state check
- **THEN** the content match remains a separately scoped observation
- **AND** it cannot replace the default save/readback/native-activation result

### Requirement: Independent configuration and supported active verification
Verify and apply's post-write verification SHALL compare selected saved configuration with the candidate, including explicit absence. Default verify SHALL report `fully_verified` with scope `saved_configuration` when selected configuration matches, and SHALL record `active` as `not_attempted` with reason `use_optional_inspect_tool`. Configuration mismatch or failed/unknown configuration readback SHALL yield failed status and a nonzero exit code. PF, interface-group and runtime deep checks SHALL be optional inspect coverage; unexecuted checks SHALL remain not_attempted, while explicit inspect SHALL report its own unsupported or unknown observations without changing the default saved-configuration status. Historical command-completion evidence SHALL remain separately reported as unavailable and SHALL NOT be used to rewrite an earlier apply result. Verification SHALL NOT perform mutation, trigger downloads or DNS resolution, refresh tables, flush PF states or claim business connectivity acceptance.

#### Scenario: Deletion is verified
- **WHEN** the candidate explicitly deletes an object
- **THEN** verification requires a complete relevant lookup confirming absence rather than merely a successful delete response
- **AND** residual-table inspection is optional and does not require every table to disappear for default completion

#### Scenario: Active inspection unsupported
- **WHEN** saved configuration matches and an optional deep inspection is unsupported or not requested
- **THEN** verify returns `fully_verified` scoped to `saved_configuration`
- **AND** default verify records active inspection as `not_attempted`; explicit inspect separately reports unsupported coverage without claiming runtime or business acceptance

#### Scenario: Independent verification observes matching saved configuration
- **WHEN** standalone verify observes the desired saved configuration without an optional deep inspection
- **THEN** it returns exit code zero with `fully_verified` scoped to `saved_configuration`
- **AND** it records active inspection as not attempted and does not claim the earlier command or runtime state succeeded
- **AND** an earlier failed or unknown apply remains unchanged

#### Scenario: A consumer check is demonstrably inapplicable
- **WHEN** complete relevant observations establish no applicable consumer under the resource's native semantics and all other applicable current-state checks pass
- **THEN** optional inspect records that consumer check as not_applicable with its reason
- **AND** default verify remains scoped to saved_configuration and does not add a consumer

#### Scenario: Consumer absence cannot be established
- **WHEN** determining whether a required consumer check applies fails or returns incomplete observations
- **THEN** optional inspect retains failed, unknown or incomplete and records the observation gap
- **AND** default verify remains scoped to saved_configuration without treating the missing deep fact as a configuration failure

#### Scenario: Current-state success cannot rescue an unconfirmed apply
- **WHEN** current-state checks all pass but a necessary action in the current apply remains failed, unknown or unconfirmed
- **THEN** apply returns failure with a nonzero exit code and stops dependent progression
- **AND** standalone verify's saved-configuration result does not rewrite the earlier apply result

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

### Requirement: Operation-specific confirmation capability admission
Plan SHALL identify the necessary save, configuration-readback and native-activation conditions and optional deep checks for each selected changed resource and operation, including enablement, disablement, deletion, activation recovery and necessary dependencies. Capability declarations SHALL specify supported provider/device conditions, observation boundaries and gaps rather than treating endpoint existence as proof of deep inspection. Known unavailable or unknown core capability SHALL produce an actionable blocked planning result that cannot authorize apply. Before its first write, apply SHALL recheck core capability for all planned stages, including required read permissions and known observation limits, and SHALL reject any unresolved core gap without partial execution. Known Alias/Gateway/Group native-response limitations SHALL emit the fixed warning on each actual activation. Optional inspection gaps SHALL be recorded in the separate inspect report and SHALL NOT alone become a write blocker. Ordinary no-change SHALL NOT create additional reload or business-test requirements.

#### Scenario: Later stage has a known core capability gap
- **WHEN** the selected candidate has an early supported stage and a later stage whose save, readback or native-activation capability cannot be obtained
- **THEN** plan identifies the gap and apply rejects the execution before any stage writes
- **AND** an optional deep inspection gap does not trigger this rejection and remains outside default admission

#### Scenario: Necessary read capability disappears after planning
- **WHEN** the target no longer permits a required read or no longer meets the supported provider conditions at apply admission
- **THEN** apply records the changed capability or unknown condition and performs zero writes

#### Scenario: No-change with unsupported optional inspection
- **WHEN** ordinary selected configuration is unchanged and only an optional active inspection is unavailable
- **THEN** the workflow records the unverified scope without adding mutation, reload, content refresh or business probes

### Requirement: Native provider response and readback
The workflow SHALL submit only the reviewed activation and required content actions, then record the native provider response and configuration readback. It SHALL NOT poll an unavailable completion endpoint or retry write, reload or refresh actions. Results SHALL distinguish successful, failed and unknown native responses and preserve any fixed deep-inspection warning. A later optional inspect SHALL NOT rewrite the default operation result.

#### Scenario: Native provider reports processing
- **WHEN** the native provider reports processing without an admitted completion endpoint
- **THEN** the result records processing/unknown and does not poll or retry
- **AND** a later optional inspect cannot rewrite the default operation result

#### Scenario: Native provider readback is unavailable
- **WHEN** native response or configuration readback is unavailable
- **THEN** the result remains unknown with the available evidence and no later mutation runs
- **AND** no automatic retry or rollback occurs

#### Scenario: Explicit failure precedes matching state
- **WHEN** an action has explicitly failed and the current table still matches the desired members
- **THEN** the action remains failed and the member observation remains separate
- **AND** no polling or content retry overrides the native failure

### Requirement: Resource-specific Alias active confirmation
The workflow SHALL preserve address-table membership, loaded-rule port expansion, effective networkgroup membership, dynamic content processing and active retirement as optional deep inspection scopes. Static address and networkgroup checks SHALL compare complete effective address semantics while preserving IPv4 and IPv6 when inspect is requested. Effective networkgroup members SHALL use selected transitions and necessary live dependencies, not unselected desired values; dynamic or unresolvable dependencies SHALL retain their incomplete status rather than becoming empty sets. Port Alias checks SHALL inspect related loaded PF rule expansion with protocol, source/destination port roles and ranges, not address tables. When inspect is requested for a disabled or deleted Alias, it SHALL report observed table absence or residual table content. An empty response that cannot distinguish an empty table from backend failure SHALL remain `empty_or_unreadable`; failed or incomplete reads SHALL retain their unknown or incomplete status. Consumer coverage SHALL remain explicitly `unobserved`, and complete retirement SHALL remain `unsupported`; inspect SHALL NOT promise to read or distinguish live-reference existence. Necessary dependency reads SHALL NOT enlarge the selected write scope.

#### Scenario: Port Alias has loaded consumers
- **WHEN** a selected port Alias is used by related loaded PF rules
- **THEN** verification checks the applicable rule identities, protocol and source/destination port expansion including ranges
- **AND** an address-table observation cannot substitute for that check

#### Scenario: Alias has no loaded port consumer
- **WHEN** a port Alias has no applicable active rule references
- **THEN** the result reports no applicable rule verification and judges the operation using its required completion evidence
- **AND** it does not create a consumer or falsely mark the rule check verified

#### Scenario: Networkgroup depends on unselected state
- **WHEN** a selected networkgroup refers to an unselected Alias whose live definition differs from the candidate's unselected desired definition
- **THEN** its effective expected members use the necessary live definition
- **AND** unresolved dynamic members or incomplete reads cannot be treated as empty or silently written to match the candidate

#### Scenario: Retired Alias leaves a table
- **WHEN** a selected Alias is disabled or deleted and inspect observes its table
- **THEN** the workflow reports the observed table state as absent, empty/unreadable, residual or failed to read, without claiming complete retirement
- **AND** live consumers remain `unobserved`/`unsupported`; no PF state is cleared and no unselected object is deleted

### Requirement: Configuration-derived dynamic Alias content actions
The workflow SHALL NOT introduce an independent forced-refresh operation for unchanged configuration. Dynamic Alias initialization, update and cache reuse SHALL follow the device's native content-processing and cache-refresh semantics; the workflow SHALL NOT require separate source identity, cache ownership/validity or per-object loading evidence. Description-only changes SHALL NOT require forced content updates or changed members. Configuration save, configuration readback, native activation and optional deep inspection SHALL remain separately represented.

#### Scenario: Newly enabled dynamic Alias has empty content
- **WHEN** initializing a newly enabled dynamic Alias yields an empty activity table
- **THEN** the workflow records native save, configuration readback and activation outcomes
- **AND** it does not add a separate source, cache or loading proof requirement

#### Scenario: Re-enable with valid reviewed cache
- **WHEN** the source is unchanged and the device performs its native cache refresh
- **THEN** the workflow records the native activation outcome without requiring a forced download or cache-validity proof

#### Scenario: Re-enable cannot prove cache suitability
- **WHEN** the workflow cannot expose the device's cache suitability as a separate fact
- **THEN** it records that deep scope as a fixed warning/result gap
- **AND** apply still follows the native cache-refresh behavior without adding an unreviewed action

#### Scenario: Source changes but members remain the same
- **WHEN** a selected source change requires content processing and the new source would yield the same members
- **THEN** the reviewed native activation remains recorded separately from any current member observation
- **AND** equal members do not become a separate source/cache/loading proof

#### Scenario: Only a description changes
- **WHEN** a dynamic Alias changes only a non-content description field
- **THEN** the workflow checks the saved field and any actually executed activation without imposing a forced download, DNS resolution or member change
- **AND** a current content match is reported separately from activation completion

#### Scenario: Native activation can recover saved source processing
- **WHEN** source B was saved but processing B failed, the caller has reconciled post-state and any potentially running prior action, and explicitly plans activation recovery
- **THEN** a new candidate can select the fixed native activation under normal drift, capability and shared-activation admission
- **AND** it records native content effects without an independent forced-refresh action or an apply-time addition
- **AND** matching old contents alone does not rewrite the earlier result

#### Scenario: Re-planning cannot repair content through native activation
- **WHEN** source B is already saved but processing B failed and the admitted native activation cannot repair or confirm the required content state
- **THEN** the result retains the native activation failure or warning and the reconciled post-state
- **AND** guidance identifies separately authorized manual handling or explicitly selected configuration reversal using reconciled, expressible recovery material under ordinary admission
- **AND** it does not invent a configuration difference, automatically toggle enablement or source, or add a forced-refresh operation

#### Scenario: Ordinary no-change does not resolve historical failure
- **WHEN** configuration matches after an earlier content-processing failure and the caller makes an ordinary no-change plan without selecting activation recovery
- **THEN** the plan adds no recovery actions and cannot reclassify the historical execution as successful
- **AND** the caller retains responsibility for reconciling the prior failed or unknown execution and deployment baseline

### Requirement: Purpose-sensitive Gateway and interface group confirmation
Default PBR Gateway and interface-group confirmation SHALL use save, configuration readback and native activation results. An optional inspect SHALL derive runtime observations from changed fields and actual use, including applicable interface/next-hop state, relevant routes, loaded PBR consumers, enabled monitoring configuration, and readable current group members or rule interfaces. It SHALL NOT present those observations as proof of registration or filter reload completion. It SHALL NOT require default-route ownership, forced monitoring, a successful ping or a newly created consumer. A saved gateway list entry alone SHALL not be reported as runtime proof; the default result SHALL state that deep inspection was not attempted. Absence of consumers SHALL be reported without inventing verification or adding rules. Optional deep inspection gaps SHALL remain in the separate inspect report and SHALL not block default writes; native-response limitations SHALL retain their fixed activation warnings. No automatic SSH, plugin, patch or privilege fallback is permitted.

#### Scenario: PBR gateway has no consumers or monitoring
- **WHEN** a selected PBR gateway has no loaded rule references and monitoring is disabled
- **THEN** default confirmation uses save, configuration readback and native activation
- **AND** optional inspect may report the no-consumer/monitoring scope without requiring default-route selection, enabling monitoring or creating a PBR rule

#### Scenario: Gateway consumers use an old next hop
- **WHEN** optional inspect finds consumers still using the old required next hop
- **THEN** the inspect report returns failed for that deep scope
- **AND** the default save/readback/native-activation result remains separately recorded

#### Scenario: Group current observations are incomplete
- **WHEN** optional inspect cannot establish a complete current member or rule-interface observation
- **THEN** the inspect report retains the available observations and marks the uncovered scope unknown
- **AND** the default result retains a fixed warning without blocking the default workflow

#### Scenario: Group has no active rule references
- **WHEN** a selected interface group has no applicable loaded consumer rules
- **THEN** default confirmation uses save, configuration readback and native activation
- **AND** optional inspect reports no applicable consumer without adding a consumer

#### Scenario: Existing APIs cannot supply deep inspection evidence
- **WHEN** optional inspect needs a fact unavailable through the admitted provider and read-only APIs
- **THEN** the inspect report records the missing fact as unknown or unsupported
- **AND** additional credentials, SSH, plugins, appliance patches or arbitrary remote commands require separate assessment and authorization
