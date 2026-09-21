## MODIFIED Requirements

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

## ADDED Requirements

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
