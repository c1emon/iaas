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

### Requirement: Explicit provider conversion boundary
The workflow SHALL convert supported native API and fixed Collection representations through a reusable pure-data boundary for the existing seven resource classes. Known boolean fields SHALL use the common deterministic conversion contract, with resource-field-specific exceptions for established native empty or inverted representations. Conversion SHALL NOT perform device operations, infer write authorization, relax standard declaration admission or determine live reference existence.

#### Scenario: Provider boolean differs from declaration syntax
- **WHEN** a supported provider field contains `"No"`, `"off"` or `"0"`
- **THEN** the field is converted to boolean false for readback
- **AND** a desired declaration that violates the existing strict boolean contract remains invalid before writes

#### Scenario: Native inverted empty flag
- **WHEN** an interface group returns `nogroup=""` under the established native field contract
- **THEN** its canonical `gui_group` value is true
- **AND** the same empty string is not accepted for an unrelated boolean or selector flag

#### Scenario: Gateway read and requested inspection agree on boolean semantics
- **WHEN** an explicitly requested existing gateway monitor-route check observes equivalent native monitor flags `0`, `"0"`, `False`, `"No"` or `"off"`
- **THEN** configuration readback and monitor-route observation apply the same boolean meaning and route-retrieval eligibility
- **AND** missing or invalid monitor flags such as `"fasle"` or `" false "` leave the relevant observation unknown rather than silently making the check not applicable
- **AND** conversion does not add optional inspection to the default workflow

### Requirement: Field-aware conversion preserves values and ambiguity
Conversion SHALL apply only the rules declared for the resource and field. It SHALL preserve identifier and descriptive strings, field absence and unsupported configuration information. It SHALL distinguish missing, null, empty and false/zero values rather than using truthiness. Multiple representations of one field SHALL be accepted together only when their converted semantics agree; conflicting sources SHALL fail explicitly. Unknown fields SHALL NOT disappear through model parsing, and resource-specific metadata exceptions SHALL NOT become global exclusions.

#### Scenario: Numeric-looking description
- **WHEN** a provider returns description or a string identifier `"001"`
- **THEN** the value remains the string `"001"`
- **AND** conversion to a number occurs only for an explicitly numeric target field

#### Scenario: Equivalent and conflicting aliases
- **WHEN** native and canonical forms of the same boolean field are both present
- **THEN** equivalent values after field conversion and any defined inversion are accepted once
- **AND** conflicting values produce an incomplete observation instead of selecting one by priority

#### Scenario: Native and canonical values are not inverted twice
- **WHEN** a provider row supplies only `disabled="0"`, only `enabled=True`, or both equivalent forms
- **THEN** each case produces canonical `enabled=True`
- **AND** all recognized source forms are consumed without leaving an extra value that can override the exported boolean

#### Scenario: Unknown zero is configuration information
- **WHEN** an identified object contains an unknown configuration field with `0` or `False`
- **THEN** the value is retained for expressibility assessment and prevents an unsupported standard reconstruction
- **AND** known metadata is excluded only under that resource's established metadata policy

#### Scenario: Absent and explicit null differ
- **WHEN** a provider field is omitted, explicitly null, or explicitly false
- **THEN** the adapter applies that field's declared policy separately to each representation
- **AND** it does not substitute a missing-field default for an invalid explicit value

#### Scenario: Native optional filter timeout is empty
- **WHEN** a native filter rule returns `statetimeout=""`
- **THEN** conversion preserves the empty optional timeout as a neutral native value without an integer conversion error
- **AND** a non-default timeout still prevents unsupported standard reconstruction
- **AND** null, malformed integers and empty strings in unrelated integer fields retain their existing rejection behavior

### Requirement: Selector and collection shapes are decoded without guessing
Dictionary selectors SHALL use selected keys as identifiers. List selectors SHALL prefer an explicit key and use a value only when the key is absent. Selection flags SHALL use deterministic boolean conversion; malformed flags, malformed items, duplicate selected identifiers and multiple selections for a single-valued field SHALL fail. CSV, newline and member-map forms SHALL be accepted only for fields declaring those shapes. Sorting SHALL be limited to established set-like fields, and conversion SHALL NOT silently deduplicate malformed input.

#### Scenario: Selector has separate identifier and label
- **WHEN** a selected option has key `wan` and display value `WAN display`
- **THEN** the canonical identifier is `wan`
- **AND** an invalid explicit key is not replaced with the display value

#### Scenario: Invalid single selection
- **WHEN** a single-valued field has two selected options, a missing selected flag or a selected flag of `"fasle"`
- **THEN** the observation remains incomplete and cannot establish absence or unchanged state

#### Scenario: Resource-specific list shapes
- **WHEN** a filter network or port field returns supported CSV, or an Alias returns its supported content member map
- **THEN** each becomes the existing resource-specific standard representation
- **AND** descriptions and unrelated scalar fields are not split, and Alias member maps are not treated as selector options

#### Scenario: Native DNAT nested padding and display descriptions
- **WHEN** DNAT source or destination returns its native empty-string `address` padding or `%network` display description beside the configured network
- **THEN** those fields do not prevent reconstruction of the configured network, port and inversion
- **AND** non-empty, null or structured address values and unknown sibling fields remain available for unsupported-configuration assessment
- **AND** the metadata exception does not become a global exclusion for other resources

#### Scenario: Native DNAT no-port-forward flag
- **WHEN** a normal DNAT rule returns `nordr="0"`, canonical `no_port_forward=False`, or both
- **THEN** the common boolean conversion yields equivalent false values and the rule remains eligible for standard reconstruction
- **AND** enabled no-port-forward mode remains unsupported, conflicting aliases fail and misspelled boolean input is not accepted

### Requirement: Conversion preserves observation and execution contracts
Conversion SHALL preserve standard declaration, identity, canonical comparison and failure semantics while extending versioned observations with independent origin and management classification. A complete internal enumeration SHALL retain identifiable built-in and unsupported native objects even when their configuration is not expressible; unavailable configuration and manual-required recovery SHALL NOT become absence or automatic recoverability through classification. Malformed enumeration, selectors or identity ambiguity SHALL retain incomplete status. Configured defaults and canonical ordering SHALL remain consistent across readback, validated desired state, verification and recovery. Conversion errors SHALL follow the safe common error boundary. A separately marked display projection SHALL NOT replace complete observations used for execution admission.

#### Scenario: Native object cannot be managed
- **WHEN** a complete list contains an internal Alias, a gateway with a usable native identity but no expressible address, or an identifiable group with unsupported empty members
- **THEN** the object remains internally observed with its identity and an unavailable standard configuration, alongside any independently established classification
- **AND** it is not removed from dependency observations or converted into a deletion candidate

#### Scenario: Invalid configuration preserves usable identity and references
- **WHEN** a completely enumerated rule lacks action or has an invalid ordinary boolean such as `enabled="fasle"`, while its identity and reference to Alias `NETS` remain reliably decodable
- **THEN** the enumeration remains complete and the object retains its identity and reference with configuration null and manual-required recovery
- **AND** the reference continues to prevent deletion of `NETS`, while that configuration failure alone does not block a plan for unrelated objects

#### Scenario: Readback normalization does not reapply desired admission
- **WHEN** an existing block or reject rule passes readback structure and expressibility checks without the declaration context required to authorize creating that rule
- **THEN** canonical normalization preserves its observed action without running creation or desired-state safety admission
- **AND** a newly supplied desired declaration still requires the existing full admission checks

#### Scenario: Equivalent inputs across workflow paths
- **WHEN** supported native and Collection forms represent the same valid standard configuration
- **THEN** they produce equal existing canonical configuration for diff and verify
- **AND** recovery retains actual before-state semantics without newly invented fields or lossy values

#### Scenario: Minimal deletion declaration
- **WHEN** a valid `state=absent` declaration contains only the existing required identity fields
- **THEN** normalization preserves that deletion declaration without requiring present-only fields or adding present-state defaults

#### Scenario: Safe readback failure
- **WHEN** model conversion fails on a sensitive provider payload
- **THEN** public reports contain only a controlled error category and safe field context
- **AND** no raw value, validation input, dynamic sensitive key or exception chain is included

### Requirement: Native activation status tolerates protocol whitespace
The fixed activation adapter SHALL trim surrounding whitespace and normalize case before comparing a native response status to `ok`. It SHALL continue rejecting missing, empty and other statuses, SHALL NOT infer success from arbitrary nonempty output, and SHALL NOT automatically retry activation.

#### Scenario: Configd returns success with trailing newlines
- **WHEN** a native activation returns `OK` followed by two newlines
- **THEN** the adapter recognizes the native success response
- **AND** configuration and business evidence retain their existing separate scope

#### Scenario: Native activation does not report success
- **WHEN** status is missing, blank, or an error message
- **THEN** activation remains failed rather than being accepted after normalization

### Requirement: Evidence-based independent resource classification
Observations for the existing supported resource classes SHALL distinguish origin as user configuration, system built-in, derived or unknown, and management capability as independently manageable, managed through source configuration, read-only or unknown. Configuration expressibility and its failure reason SHALL remain independent of both classifications. Relevant observations SHALL distinguish persistent configuration, dynamic contents and runtime state without treating dynamic contents as proof of read-only configuration. Classification SHALL record safe evidence categories and a source association when reliably available, using verified native semantics for the supported provider and device version. Names, UUIDs, dynamic addresses and conversion failures alone SHALL NOT establish system origin or management capability. Missing, conflicting or unrecognized classification evidence SHALL leave the affected dimension unknown and SHALL NOT grant management rights.

#### Scenario: Internal and external Alias differ
- **WHEN** verified native semantics identify an internal system Alias and a separately configured external Alias
- **THEN** the system Alias receives its evidenced origin and management classification
- **AND** the external Alias is not classified as system-owned merely from its type or a system-like name

#### Scenario: Preconfigured editable rule
- **WHEN** a rule was supplied as a default but is an independently editable persistent configuration object under the supported native model
- **THEN** it is treated as ordinary configuration with independently established management capability
- **AND** its default presence neither hides it nor authorizes IaaS adoption

#### Scenario: Dynamic values do not establish origin
- **WHEN** a user-configured URL Alias has changing members or a gateway has a dynamically obtained address
- **THEN** configuration origin and management capability are assessed separately from those dynamic values
- **AND** missing gateway expressibility remains a separate limitation rather than proof of system read-only origin

#### Scenario: Conflicting or unsupported evidence
- **WHEN** classification markers conflict, are missing, use an unsupported representation or cannot be tied to verified supported-version semantics
- **THEN** the affected classification dimension remains unknown with a safe reason
- **AND** neither a matching object name nor successful configuration conversion supplies the missing management evidence

### Requirement: Complete internal observations with scoped display projection
The workflow SHALL retain all identifiable objects within the bounded relevant internal enumeration, including system and derived objects and their reliably decoded references. Read results SHALL identify the enumeration source and scope and SHALL distinguish complete internal observations from a display projection. Configuration endpoint enumeration SHALL NOT be presented as complete active PF rule enumeration. Necessary dependency and reverse-reference checks SHALL use complete relevant observations regardless of display options. Filtered display results SHALL NOT be accepted as complete execution state or evidence of absence.

#### Scenario: Hidden system dependency
- **WHEN** a user rule references a system Alias or interface group hidden by the default display
- **THEN** the target remains available to the existing supported reference checks
- **AND** hiding it neither causes a false missing-reference result nor permits deletion prohibited by an observed reverse reference

#### Scenario: Configuration-only enumeration
- **WHEN** filter objects are read from the supported configuration collection
- **THEN** the report identifies that configuration scope
- **AND** enabling system display does not claim to enumerate all automatically generated or active PF rules

#### Scenario: Display result supplied as full observation
- **WHEN** a filtered read result is presented where complete execution observations are required
- **THEN** it is rejected as an unsuitable observation shape or scope
- **AND** omitted rows are not interpreted as absent resources

### Requirement: Minimal reference support for non-expressible system objects
For confirmed system-built-in or derived Alias and interface-group objects without expressible standard configuration, the workflow SHALL support existing rule references when verified native evidence establishes a stable reference identity, the required address, port or interface-group role, and any address-family or dependency facts needed by the existing reference checks. Reference support SHALL remain separate from standard configuration expressibility and independent management capability. The workflow SHALL preserve necessary reverse-reference, transitive dependency and cycle protections and SHALL NOT invent configuration or assume absent dependencies from unavailable evidence. Unknown origin, malformed native observations and failed user-configuration conversion SHALL NOT receive this system-reference exception. Relevant reference semantics SHALL be bound to candidate observations and checked for drift before affected writes.

#### Scenario: Rule uses a system address Alias or group
- **WHEN** a rule references an observed non-expressible system address Alias in an address field or a system interface group in an interface field, with reliable role evidence and complete necessary dependency facts
- **THEN** the supported reference is admitted without requiring a fictitious standard declaration for the target
- **AND** the target remains non-expressible and gains no independent write authorization

#### Scenario: System address Alias is used as a port
- **WHEN** a rule uses an Alias with only verified address-reference support in a port field
- **THEN** admission rejects the incompatible role despite the target's confirmed system classification

#### Scenario: System reference evidence is insufficient
- **WHEN** target identity is ambiguous or required role, address-family or dependency evidence is missing or conflicting
- **THEN** the affected reference cannot be admitted
- **AND** system classification does not substitute for the missing evidence or disable reverse-reference and cycle protection

#### Scenario: Reference role changes after review
- **WHEN** a system dependency's required reference role or supporting evidence changes or becomes unavailable after candidate review
- **THEN** execution blocks the affected write through its relevant dependency drift checks
- **AND** unchanged target identity or origin alone does not make the reference safe

### Requirement: Default resource view and explicit system inclusion
Read SHALL default to hiding object details only when origin is confirmed as system built-in or derived and management capability is confirmed as source-managed or read-only. User configuration, independently manageable objects, unknown origin or management capability, and unsupported user configuration SHALL remain visible. The read-only `include_system` option SHALL be a strict boolean defaulting to false; the local read command SHALL expose it as `--include-system`. Enabling it SHALL show all objects within the existing selection and observed scope without expanding endpoints, resource selection or write authorization. Other workflow operations SHALL reject the display option. An explicitly selected object resolvable under the existing identity contract SHALL return its detail and limitations even when hidden in the default class listing.

#### Scenario: Default class listing
- **WHEN** a selected class contains independently editable configuration, confirmed non-independent system objects, unsupported user configuration and an unknown-origin object
- **THEN** only the confirmed non-independent system object details are hidden
- **AND** the other objects and their limitations remain visible, with hidden objects represented in the summary

#### Scenario: Include system objects
- **WHEN** read is requested with `include_system=true`
- **THEN** system and derived details are included within the same selected scope
- **AND** no additional management rights, resource reads or PF enumeration are implied

#### Scenario: Exact system object requested
- **WHEN** read explicitly selects an existing system object using an accepted exact identity
- **THEN** its detail and management restriction are returned without requiring the display option
- **AND** the result does not imply that the object is absent because the default class view hides it

#### Scenario: Invalid or misplaced display option
- **WHEN** `include_system` is not a boolean or is supplied to plan, apply or verify
- **THEN** input validation rejects it before any device operation

### Requirement: Classification-aware scoped summaries
Read reports SHALL separately identify enumerated, selection-matched, displayed and hidden object counts and whether display filtering occurred. Origin and management counts SHALL be separate dimensions; known user configuration expressibility failures and unknown classifications SHALL remain explicit. Confirmed system or derived objects SHALL NOT inflate a user-configuration unsupported count, and their own conversion or observation limitations SHALL remain available in scoped summaries and full detail. Count completeness SHALL follow actual observation coverage, and filtering SHALL NOT turn failed or incomplete observations into success. Resource-level `read_only` SHALL retain its meaning that the operation does not write, independently of object management classification.

#### Scenario: Hidden counts remain accountable
- **WHEN** a complete selected class contains hidden system objects
- **THEN** displayed plus hidden counts equal the selection-matched count
- **AND** enumeration totals retain their own scope rather than being replaced by the displayed count

#### Scenario: Incomplete enumeration or unknown objects
- **WHEN** enumeration is incomplete or some objects cannot be classified
- **THEN** the report retains incomplete coverage or unknown classification as applicable and reports only supported counts
- **AND** it does not infer missing objects to be system-generated or report full-device coverage

#### Scenario: System conversion limitation
- **WHEN** an identified system object cannot be converted to a standard declaration
- **THEN** its conversion limitation remains recorded separately from its confirmed classification
- **AND** the default summary does not count that object as an unsupported user declaration or erase its limitation

### Requirement: Management classification admission and drift
An existing object SHALL require reliable independent-management evidence before admission to independent mutation, adoption or activation recovery, in addition to ordinary declaration, selection, ownership and confirmation checks. Source-managed, read-only or unknown-management targets SHALL be blocked with a safe reason and known source guidance, without silently skipping selected work or selecting the source for mutation. Origin alone SHALL NOT grant or deny management rights. Complete relevant absence SHALL continue to permit ordinary supported new-object creation. Unselected classification gaps SHALL NOT block unrelated work unless required dependency or affected-state evidence is unavailable. Reviewed candidates SHALL bind relevant classification semantics, and execution SHALL re-check relevant management and source changes at its existing read boundaries before further mutation. Display options SHALL NOT change candidate semantics, reference checks or drift outcomes.

Independent-management evidence SHALL cover the lifecycle operations needed by the existing standard declaration model, and admission SHALL remain limited to the supported requested operation and fields. Permission to override a subset of settings SHALL NOT establish deletion, recreation or activation-recovery capability. In this change, partially editable objects whose operation boundary cannot be represented reliably SHALL have unknown management capability with a controlled partial-management limitation, SHALL remain visible by default and SHALL be blocked from independent operations; they SHALL NOT be relabeled as fully read-only or source-managed without corresponding native evidence.

#### Scenario: Explicit non-independent target
- **WHEN** the caller explicitly selects a known source-managed or read-only object for independent modification
- **THEN** admission blocks that operation and reports the management reason and any reliably known source configuration
- **AND** explicit selection or adoption does not override that restriction

#### Scenario: Management evidence missing despite expressibility
- **WHEN** an existing target has expressible configuration but unknown management capability
- **THEN** it cannot obtain independent mutation admission from successful conversion alone
- **AND** ordinary unselected unrelated unknown objects do not automatically block other supported work

#### Scenario: Partial settings override does not allow independent lifecycle operations
- **WHEN** a system object permits overrides of a few settings but the adapter cannot reliably represent its operation boundary
- **THEN** it remains visible with unknown management capability and a partial-management limitation
- **AND** explicit managed or adopt selection cannot authorize independent update, delete, recreation or activation recovery using that partial evidence

#### Scenario: New user object
- **WHEN** a complete relevant lookup confirms a selected new identity absent and the desired declaration satisfies existing supported creation admission
- **THEN** creation remains eligible without inventing a live origin classification
- **AND** necessary reference and ownership constraints still apply

#### Scenario: Capability changes after review
- **WHEN** a reviewed independently manageable target becomes read-only, source-managed or unknown before execution, or its relevant source association changes
- **THEN** the workflow blocks further mutation of that target and requires a new reviewed plan
- **AND** unchanged canonical configuration does not bypass the classification drift

#### Scenario: Origin label correction preserves management admission
- **WHEN** only an object's origin label is corrected while independent management capability, its supporting evidence and relevant source association remain unchanged
- **THEN** that label change alone does not block execution
- **AND** ordinary configuration, dependency, ownership and activation checks still apply

#### Scenario: Newly created object gains observed classification
- **WHEN** an admitted creation changes a confirmed absent identity into an observed independently manageable object matching the reviewed declaration
- **THEN** the expected absence-to-presence and management classification transition is accepted
- **AND** missing or incompatible management evidence remains failed or unknown and stops further dependent mutation

### Requirement: Classification-constrained recovery and unchanged verification scope
Automatic inverse candidates SHALL require independent management capability and adequate actual before-state and confirmed after-state evidence under the existing recovery contract. System or derived observations SHALL NOT become independent deletion or recreation targets merely because they were enumerated or classified. Source-managed effects SHALL be handled only through a separately explicitly selected supported source configuration under normal planning and recovery admission. Classification SHALL NOT upgrade manual-required recovery, establish activation completion, confirm runtime behavior or rewrite earlier execution results. Saved-configuration verification and optional active inspection SHALL retain their existing separate scopes.

#### Scenario: Derived object appears in observations
- **WHEN** recovery material includes observations of a non-independent derived object
- **THEN** no independent inverse create or delete is generated for that object
- **AND** handling its source requires explicit supported source selection rather than automatic scope expansion

#### Scenario: Reverse newly created independent object
- **WHEN** the original execution created an independently manageable user object from confirmed absence and current observations support safe reversal
- **THEN** an explicit inverse deletion remains available under normal reference, classification and drift checks

#### Scenario: Recreate a deleted independent user object
- **WHEN** recovery material retains the deleted user's actual before-configuration and management evidence, identifies the original execution and confirmed deletion outcome, and a complete current lookup confirms the identity still absent
- **THEN** an explicit inverse creation is eligible under supported recreation, declaration and reference admission without requiring live classification from a nonexistent object
- **AND** after creation, ordinary configuration and management readback requirements apply

#### Scenario: Deleted identity has been reused
- **WHEN** recovery would recreate a deleted object but current observation finds another object at its former identity or cannot confirm absence
- **THEN** automatic inverse creation is blocked
- **AND** recovery does not reinterpret the operation as an update of the new occupant

#### Scenario: Classification does not repair an earlier failure
- **WHEN** a previously manual-required or failed observation gains a confirmed system classification
- **THEN** the classification explains the resource boundary without claiming recovery, activation or business success
- **AND** prior execution evidence remains unchanged

### Requirement: Versioned classification contract migration
The classification-aware candidate, result and recovery contracts SHALL use a new explicit format version. Execution SHALL reject older candidates or new-version execution material lacking required management classification with re-planning guidance rather than synthesizing authorization at apply time. Old recovery evidence SHALL remain preservable but SHALL NOT be silently promoted into classification-aware automatic recovery; handling SHALL require explicit reconciliation and a new admissible plan. Standard resource declarations, existing request semantics and the operation meaning of `read_only` SHALL remain unchanged. Complete observation artifacts and filtered read views SHALL have distinguishable scope and contracts.

Both formal runtime and local workflow entrypoints SHALL emit explicitly versioned results with equivalent complete-observation and display-projection scope semantics. Local execution identity differences SHALL NOT remove the result version or change the meaning of these scope markers.

#### Scenario: Runtime and local results share scope semantics
- **WHEN** equivalent read requests are processed through the formal runtime and local entrypoints
- **THEN** both results identify the new result version and distinguish the complete observation artifact from the default or system-inclusive view
- **AND** each entrypoint's plan and verify results retain explicit result-version identification rather than unversioned legacy shapes

#### Scenario: Old candidate or omitted classification
- **WHEN** apply or verify receives an old candidate, or a new-version candidate lacks required classification context
- **THEN** validation rejects it with compatibility and re-planning guidance
- **AND** no device mutation or implicit candidate upgrade occurs

#### Scenario: Old recovery evidence retained
- **WHEN** the caller supplies recovery evidence from the earlier format
- **THEN** it is not deleted, rewritten as successful or automatically assigned management capability
- **AND** automatic recovery admission is rejected with guidance to reconcile original and current state before preparing an explicit supported plan
