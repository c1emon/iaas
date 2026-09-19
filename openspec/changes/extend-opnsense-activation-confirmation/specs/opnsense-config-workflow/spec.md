## MODIFIED Requirements

### Requirement: Reviewed candidate remains the execution input
Plan SHALL produce a self-contained candidate containing resolved standard declarations, selected identities, fixed execution stages, relevant live observations, target connection identity and runtime identity. Each actual stage SHALL additionally bind its required confirmation conditions, supplementary checks, finite observation policy and any content actions derived from selected configuration changes. Content actions SHALL identify selected resource identity, candidate source configuration, trigger and permitted cache policy. Apply SHALL consume only that explicit reviewed candidate and verify its caller-supplied reviewed digest, target, runtime digest, platform and format compatibility before writes. It SHALL NOT recompile policy, load replacement desired inputs, silently replan, add content actions or turn an allowed cache reuse into an unreviewed refresh. Available source revision and dirty state SHALL be recorded honestly; unavailable provenance SHALL remain unavailable. Credentials SHALL be injected separately and SHALL NOT be saved in the candidate. Candidates missing the required new confirmation contract SHALL be rejected with re-planning guidance rather than implicitly upgraded during execution.

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

#### Scenario: Reviewed cache reuse becomes invalid
- **WHEN** a candidate permits cache reuse but the required source or validity condition no longer holds before execution
- **THEN** apply performs no writes and requires re-planning
- **AND** it does not replace the reviewed reuse with a download or DNS resolution action

### Requirement: Relevant drift and shared activation admission
Apply SHALL re-read affected objects and necessary references before the first write and reject relevant changes or unknown required state compared with the reviewed candidate. Shared activation effects SHALL be disclosed independently of object write selection. Detected pending changes outside the reviewed activation authorization SHALL stop execution. Where automatic detection is unavailable, the result SHALL say unknown and require an explicit caller check conclusion bound to the target, candidate and current execution before writes. This conclusion SHALL NOT override detected conflicts or be reported as device evidence. Callers SHALL serialize target writes throughout saving, activation and confirmation waits; relevant checks SHALL continue across stage boundaries and waits and stop on observed external changes without claiming transaction isolation or requiring a whole-device per-object snapshot. A caller conclusion SHALL NOT substitute for activation completion evidence, and a confirmation failure SHALL NOT authorize a broader reload or new credentials.

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
Apply SHALL report persistence, activation completion, saved-configuration verification, content processing, active-state verification and business acceptance separately, including failed, unconfirmed, unknown and not-attempted outcomes with their evidence and uncovered scope. Request acceptance alone SHALL NOT be reported as confirmed activation. Current membership equality, a nonempty table, a timestamp change or matching saved configuration alone SHALL NOT promote accepted or unconfirmed activation to success. Completion SHALL be determined by the published resource-operation evidence combination, using reliable synchronous completion or completion evidence associated with the attempted action and any required active observations. Failed or unconfirmed necessary completion SHALL stop dependent stages and return nonzero. A CRUD failure SHALL stop subsequent mutation and activation; bounded readback SHALL record what can still be confirmed. Timeout, cancellation or unavailable readback SHALL preserve unknown outcomes without automatic batch retry or rollback. Ordinary no-op execution SHALL NOT reload; activation recovery SHALL require an explicit reviewed candidate and normal admission checks, and SHALL NOT authorize independent forced content refresh.

#### Scenario: Save succeeds and activation fails
- **WHEN** the selected changes are saved but activation fails
- **THEN** the result reports saved configuration and failed activation separately, stops dependent stages and returns a failure status
- **AND** it does not report the previous saved configuration as automatically restored

#### Scenario: Endpoint only acknowledges invocation
- **WHEN** an activation endpoint returns ok without reliable evidence of underlying reload completion
- **THEN** the workflow requires the operation's specified completion evidence or records activation as unconfirmed
- **AND** reading saved configuration or matching active members alone cannot establish completion of that invocation

#### Scenario: Partial write with lost connectivity
- **WHEN** a write times out and bounded readback cannot reach the appliance
- **THEN** attempted work and unknown outcomes remain in the result and no later mutation or automatic retry runs

#### Scenario: Explicit no-change activation recovery
- **WHEN** a newly reviewed candidate explicitly requests activation recovery for unchanged saved configuration
- **THEN** the selected fixed target can activate only after drift, necessary confirmation capability and shared activation admission succeeds
- **AND** ordinary no-change candidates and read-only operations do not activate
- **AND** activation recovery does not add independent forced downloading or DNS resolution; any native content-processing effects of the fixed activation are disclosed and bound to the new candidate
- **AND** where that native activation cannot satisfy necessary content conditions with sufficient evidence, planning returns a blocked result with manual-action or explicitly reviewed configuration-reversal guidance rather than a generic re-planning loop

#### Scenario: Successful content update leaves equal members
- **WHEN** a required content update has valid completion and loading evidence and the resulting members equal the previous members
- **THEN** the update and applicable active-state checks can be confirmed independently
- **AND** equality neither skips the required action nor causes an otherwise successful update to fail

#### Scenario: Failed content update leaves matching old members
- **WHEN** a required content update explicitly fails but the previous members still match an expected current-state check
- **THEN** the content match remains recorded while the update remains failed and the stage does not succeed
- **AND** the match cannot promote activation or refresh completion or allow dependent stages to continue

### Requirement: Independent configuration and supported active verification
Verify and apply's post-write verification SHALL compare selected saved configuration with the candidate, including explicit absence, and perform supported resource-specific current-state checks with stated coverage. Configuration mismatch, failed, unknown or incomplete applicable current-state checks, and unsupported required current-state checks SHALL yield failed status and a nonzero exit code. If required current-state checks succeed and only supplementary checks are unsupported, standalone verify SHALL return completed_with_unverified with exit code zero and explicit uncovered scope. If all applicable current-state checks succeed, standalone verify SHALL return fully_verified with exit code zero, scoped only to current-state verification. A check SHALL be not_applicable only when native semantics and complete relevant observations establish that it does not apply; such checks SHALL be excluded from pass, failure and unverified counts without being marked verified. Missing permission, incomplete reads and inability to determine consumer presence SHALL NOT establish non-applicability. Historical command-completion evidence SHALL NOT be a required input or check for standalone verify and its absence SHALL NOT fail or downgrade the current-state aggregate; it SHALL remain separately reported as unavailable. These standalone aggregation rules SHALL NOT waive apply's required action-completion evidence, revise an earlier apply result or advance caller deployment records. Verification SHALL NOT perform mutation, trigger downloads or DNS resolution, refresh tables, flush PF states or claim business connectivity acceptance.

#### Scenario: Deletion is verified
- **WHEN** the candidate explicitly deletes an object
- **THEN** verification requires a complete relevant lookup confirming absence rather than merely a successful delete response
- **AND** required active retirement follows resource semantics, not a universal assumption that every table must disappear

#### Scenario: Active inspection unsupported
- **WHEN** saved configuration matches but a supplementary active inspection is not supported
- **THEN** results retain saved-configuration success and mark that active inspection unverified with its scope
- **AND** the task cannot be described as fully verified or as business acceptance

#### Scenario: Independent verification observes matching members
- **WHEN** standalone verify observes the desired configuration and current members but has no completion evidence for an earlier reload or content update
- **THEN** it reports the current matches and the unavailable historical completion evidence separately
- **AND** it returns exit code zero with fully_verified for fully covered current-state checks, or completed_with_unverified when only supplementary current-state checks are unsupported
- **AND** it neither claims the earlier command succeeded nor submits a new command to make that claim
- **AND** an earlier failed or unknown apply remains unchanged

#### Scenario: A consumer check is demonstrably inapplicable
- **WHEN** complete relevant observations establish no applicable consumer under the resource's native semantics and all other applicable current-state checks pass
- **THEN** standalone verify records that consumer check as not_applicable with its reason and returns fully_verified for the current-state scope with exit code zero
- **AND** that check is not counted as passed or unverified, and apply still requires its own necessary action-completion evidence

#### Scenario: Consumer absence cannot be established
- **WHEN** determining whether a required consumer check applies fails or returns incomplete observations
- **THEN** the condition remains failed, unknown or incomplete and verification returns failed with a nonzero exit code
- **AND** the workflow does not use not_applicable to bypass that observation failure

#### Scenario: Current-state success cannot rescue an unconfirmed apply
- **WHEN** current-state checks all pass but a necessary action in the current apply remains failed, unknown or unconfirmed
- **THEN** apply returns failure with a nonzero exit code and stops dependent progression
- **AND** standalone verify's current-state aggregation does not override the missing action evidence

## ADDED Requirements

### Requirement: Operation-specific confirmation capability admission
Plan SHALL identify necessary completion evidence and optional active checks for each selected changed resource and operation, including enablement, disablement, deletion, activation recovery and necessary dependencies. Capability declarations SHALL specify supported provider/device conditions, observation boundaries and gaps rather than treating endpoint existence as proof of completion. Known unavailable or unknown necessary capability SHALL produce an actionable blocked planning result that cannot authorize apply. Before its first write, apply SHALL recheck necessary capability for all planned stages, including required read permissions and known observation limits, and SHALL reject any unresolved necessary gap without partial execution. An unsupported optional check SHALL NOT alone become a write blocker. Ordinary no-change SHALL NOT create additional reload or business-test requirements.

#### Scenario: Later stage has a known capability gap
- **WHEN** the selected candidate has an early supported stage and a later stage whose required completion evidence cannot be obtained
- **THEN** plan identifies the gap and apply rejects the execution before any stage writes
- **AND** it does not attempt the early stage merely to discover the known later limitation

#### Scenario: Necessary read capability disappears after planning
- **WHEN** the target no longer permits a required read or no longer meets the supported provider conditions at apply admission
- **THEN** apply records the changed capability or unknown condition and performs zero writes

#### Scenario: No-change with unsupported optional inspection
- **WHEN** ordinary selected configuration is unchanged and only an optional active inspection is unavailable
- **THEN** the workflow records the unverified scope without adding mutation, reload, content refresh or business probes

### Requirement: Bounded read-only completion observation
The workflow SHALL submit only the reviewed activation and required content actions, then use bounded read-only observation with both a total deadline and an attempt limit. Each request and wait interval SHALL be bounded by the remaining deadline. Results SHALL distinguish known processing, explicit failure, timeout or unreadable unknown and confirmed completion. Known failure SHALL NOT be erased by subsequent matching old state. New complete observations with unchanged content SHALL NOT be classified as stale solely because their values match previous values, while cached old observations and truncated results SHALL NOT confirm the attempted action. Exhausted observation bounds SHALL NOT authorize write, reload or refresh retries.

#### Scenario: Completion is delayed
- **WHEN** the first observation reports processing and later valid completion evidence arrives within the reviewed limits
- **THEN** the stage can complete using that evidence and its required current-state checks
- **AND** polling has not resubmitted activation, content update or resource writes

#### Scenario: Observation deadline expires
- **WHEN** the deadline or attempt limit is reached without sufficient completion evidence
- **THEN** the result remains unknown with the last confirmed observations and dependent progression stops
- **AND** no automatic retry or rollback occurs and timeout is not represented as appliance cancellation

#### Scenario: Explicit failure precedes matching state
- **WHEN** an action has explicitly failed and the current table still matches the desired members
- **THEN** the action remains failed without polling for a later content match to override its result

### Requirement: Resource-specific Alias active confirmation
The workflow SHALL distinguish address-table membership, loaded-rule port expansion, effective networkgroup membership, dynamic content processing and active retirement. Static address and networkgroup checks SHALL compare complete effective address semantics while preserving IPv4 and IPv6. Effective networkgroup members SHALL use selected transitions and necessary live dependencies, not unselected desired values; dynamic or unresolvable dependencies SHALL retain their capability or incomplete status rather than becoming empty sets. Port Alias checks SHALL inspect related loaded PF rule expansion with protocol, source/destination port roles and ranges, not address tables. Disabled and deleted Alias checks SHALL distinguish absent objects, empty tables, residual tables, live references and failed reads; table disappearance SHALL be required only where native operation semantics require it. Necessary dependency reads SHALL NOT enlarge the selected write scope.

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
- **WHEN** a selected Alias is disabled or deleted and a table remains visible
- **THEN** the workflow evaluates remaining references and table state under that operation's native retirement conditions
- **AND** it distinguishes residual and empty tables from absent objects and read failures without clearing PF states or deleting unselected objects

### Requirement: Configuration-derived dynamic Alias content actions
The workflow SHALL NOT introduce an independent forced-refresh operation for unchanged configuration. Necessary content initialization, update or cache reuse SHALL be derived from selected configuration transitions and bound into the candidate with resource identity, source, trigger, permitted cache conditions and completion/loading requirements. A newly enabled dynamic Alias requiring initialization SHALL have successful source processing and loading evidence; valid empty content SHALL require successful processing evidence rather than an empty table alone. Re-enablement with unchanged source SHALL require loading and SHALL permit cache reuse only when the candidate allows it and source ownership and applicable validity conditions are demonstrable; otherwise the plan SHALL require update and loading evidence. Source changes requiring active content SHALL require processing the new source and loading its result, not old-source cache reuse. Description-only changes SHALL NOT require forced content updates or changed members, while any actual activation SHALL still require its own completion evidence. Configuration application, content processing, allowed cache reuse and active-table state SHALL remain separate outcomes.

#### Scenario: Newly enabled dynamic Alias has empty content
- **WHEN** initializing a newly enabled dynamic Alias yields an empty activity table
- **THEN** success requires evidence of successful processing of the candidate source and loading under that type's semantics
- **AND** failed retrieval followed by an empty table does not pass

#### Scenario: Re-enable with valid reviewed cache
- **WHEN** the source is unchanged, the candidate permits reuse and current evidence establishes applicable cache source and validity conditions
- **THEN** the workflow records cache reuse and confirms required loading without requiring a forced download

#### Scenario: Re-enable cannot prove cache suitability
- **WHEN** planning cannot establish that a cache meets the required source or validity conditions
- **THEN** it plans required update and loading or reports the necessary capability gap
- **AND** apply cannot silently use that cache or substitute a new unreviewed update

#### Scenario: Source changes but members remain the same
- **WHEN** a selected source change requires content processing and the new source would yield the same members
- **THEN** the reviewed update still requires new-source processing and loading evidence
- **AND** old cache or equal members alone cannot establish completion

#### Scenario: Only a description changes
- **WHEN** a dynamic Alias changes only a non-content description field
- **THEN** the workflow checks the saved field and any actually executed activation without imposing a forced download, DNS resolution or member change
- **AND** a current content match is reported separately from activation completion

#### Scenario: Native activation can recover saved source processing
- **WHEN** source B was saved but processing B failed, the caller has reconciled post-state and any potentially running prior action, and explicitly plans activation recovery
- **THEN** a new candidate can select the fixed native activation only if its admitted semantics can perform the missing source processing and the necessary completion and loading evidence can be obtained
- **AND** the candidate records source B, those native effects and confirmation conditions before execution, without an independent forced-refresh action or an apply-time addition
- **AND** execution still requires normal drift, capability and shared-activation admission; matching old contents alone cannot confirm it

#### Scenario: Re-planning cannot repair content through native activation
- **WHEN** source B is already saved but processing B failed and the admitted native activation cannot repair or confirm the required content state
- **THEN** an activation-recovery plan returns a nonzero blocked result and manual_required disposition with the specific missing facts
- **AND** guidance identifies separately authorized manual handling or explicitly selected configuration reversal using reconciled, expressible recovery material under ordinary admission, without promising either has already succeeded
- **AND** it does not merely request another identical plan, invent a configuration difference, automatically toggle enablement or source, or add a forced-refresh operation

#### Scenario: Ordinary no-change does not resolve historical failure
- **WHEN** configuration matches after an earlier content-processing failure and the caller makes an ordinary no-change plan without selecting activation recovery
- **THEN** the plan adds no recovery actions and cannot reclassify the historical execution as successful
- **AND** the caller retains responsibility for reconciling the prior failed or unknown execution and deployment baseline

### Requirement: Purpose-sensitive Gateway and interface group confirmation
PBR Gateway confirmation SHALL derive required runtime observations from the changed fields and actual use, including applicable interface/next-hop state, relevant routes, loaded PBR consumers and enabled monitoring configuration. It SHALL NOT require default-route ownership, forced monitoring, a successful ping or a newly created consumer. A saved gateway list entry alone SHALL NOT prove application. Interface group confirmation SHALL distinguish saved configuration, registration with correct membership and filter reload completion; where related loaded rules exist, it SHALL check their interface matching semantics. Absence of consumers SHALL be reported without inventing verification or adding rules. Necessary unobservable facts SHALL follow the same pre-write capability admission as other resources, without an automatic SSH, plugin, patch or privilege fallback.

#### Scenario: PBR gateway has no consumers or monitoring
- **WHEN** a selected PBR gateway has no loaded rule references and monitoring is disabled
- **THEN** confirmation uses the applicable operation completion and necessary interface/next-hop or route observations
- **AND** it does not require default-route selection, enable monitoring or create a PBR rule merely for verification

#### Scenario: Gateway consumers use an old next hop
- **WHEN** a gateway change requires updated loaded PBR next-hop semantics but consumers still reflect the old required state
- **THEN** the operation cannot be confirmed from the saved gateway entry or ping alone
- **AND** bounded observation and final failure or unknown reporting preserve the incomplete scope

#### Scenario: Group registers but filter reload fails
- **WHEN** interface group registration and membership are confirmed but its required filter reload fails
- **THEN** the result retains registration success and failed activation separately and dependent stages stop

#### Scenario: Group has no active rule references
- **WHEN** a selected interface group has no applicable loaded consumer rules
- **THEN** confirmation checks required registration, membership and reload evidence without claiming successful rule verification or adding a consumer

#### Scenario: Existing APIs cannot supply completion evidence
- **WHEN** a resource operation needs a fact unavailable through the admitted provider and read-only APIs
- **THEN** the workflow reports the missing fact and blocks the affected execution before writes
- **AND** additional credentials, SSH, plugins, appliance patches or arbitrary remote commands require separate assessment and authorization
