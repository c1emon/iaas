## Purpose

Define a caller-authorized PVE template lifecycle with fixed build inputs, reconnectable execution evidence, current-object association, and cleanup that respects native state ownership without owning a site publication registry.

## ADDED Requirements

### Requirement: Independent fixed template preview
The system SHALL expose offline validation and online read/plan/apply/verify for template lifecycle operations independently of VM declarations and OpenTofu state.

#### Scenario: Review a new build
- **WHEN** a caller selects a recipe, base-image URL/checksum, target, storage, bridge, version and new VMID
- **THEN** plan SHALL retain a versioned fixed-input build preview and required runtime/helper identities without creating a VM or modifying the node
- **AND** apply SHALL require the exact preview association, a new execution identity and explicit caller authorization/serialization context
- **AND** it SHALL reject input overrides, incompatible helpers and occupied VMIDs rather than install prerequisites or replace objects

#### Scenario: Verify build prerequisites
- **WHEN** an authorized build begins
- **THEN** it SHALL validate checksum before image customization/import and verify required helper permissions, bridge, storage capability and declared free-space thresholds
- **AND** cache and work writes SHALL be reported separately from VM changes
- **AND** insufficient or unknown required facts SHALL stop dependent phases without claiming future storage availability

#### Scenario: Storage plugin writes CLI logs
- **WHEN** template preflight or the locked worker checks storage prerequisites
- **THEN** storage facts SHALL come from the local PVE HTTPS storage-status API rather than plugin-contaminated CLI stdout
- **AND** the node-root probe SHALL authenticate only to loopback after validating the locally configured server certificate, with authentication material retained only in memory
- **AND** authentication, TLS, HTTP and malformed response failures SHALL block dependent work without a CLI fallback
- **AND** actual cache/work filesystem checks SHALL remain local and the worker SHALL repeat storage checks after taking its node mutation lock

### Requirement: Durable remotely queryable template execution
The node executor SHALL persist execution identity and fixed-input association before facility mutation, and SHALL preserve queryable phase and object evidence independently of the controller connection.

#### Scenario: Controller disconnects during a build
- **WHEN** SSH disconnects or the controller is cancelled while a remote build may continue
- **THEN** the controller SHALL NOT claim the remote operation stopped or succeeded
- **AND** a later read SHALL associate the original execution with its available remote task, completed phases, confirmed created objects and unknown effects
- **AND** no reconnect or node reboot SHALL automatically replay the build

#### Scenario: Duplicate execution submission
- **WHEN** an existing execution ID is submitted again
- **THEN** matching fixed inputs SHALL only return the existing execution observation and SHALL NOT start another worker
- **AND** conflicting inputs SHALL be rejected

#### Scenario: Workers and cleanup compete on a node
- **WHEN** different executions or cleanup actions target the same node protection domain
- **THEN** each worker SHALL hold the shared node mutation lock from before its first side effect through completion of its mutation phases
- **AND** cleanup SHALL acquire the same lock and recheck original-task inactivity and object ownership inside it
- **AND** short execution-record admission locks SHALL be separate from this lifecycle lock, so reads and matching duplicate submissions can report the current execution without waiting for the build to finish
- **AND** a worker SHALL recheck mutable prerequisites after acquiring the lock and SHALL fail within a bounded wait rather than rely only on submission-time checks

#### Scenario: Interrupted evidence collection
- **WHEN** execution or collection stops before a final receipt is available
- **THEN** existing private logs and receipts SHALL be retained and missing conclusions SHALL remain unknown
- **AND** object existence or a stale running record alone SHALL NOT prove completion or current activity

### Requirement: Template facts and publication are separate
The system SHALL return construction and configuration facts separately from clone/guest verification and caller-owned publication decisions.

#### Scenario: Deliver a new template for acceptance
- **WHEN** construction and required configuration checks complete
- **THEN** the result SHALL bind version, target, object identity, disk/hardware/cloud-init facts, source and execution to a built-and-verified outcome
- **AND** identity-cleaning steps SHALL require actual execution evidence rather than assuming cleanup from template presence
- **AND** unperformed clone and business checks SHALL remain explicitly unperformed, without declaring the template published

#### Scenario: Observe a historical template
- **WHEN** a caller explicitly selects an existing template
- **THEN** the system SHALL return an observation record suitable for caller registration without requiring a rebuild
- **AND** absent build or cleaning history SHALL remain unknown rather than be represented as a successful historical build
- **AND** missing required current-object identity SHALL prevent use as a verified clone reference

#### Scenario: Validate an unpublished template
- **WHEN** a caller authorizes a bounded temporary verification VM using a pending template record
- **THEN** the reference SHALL be admitted only for that explicit verification purpose and scope
- **AND** normal cloning SHALL still require the caller's current available-version admission

### Requirement: Template references identify the current object
The system SHALL bind template records to observable current-object identity beyond node, VMID and template flag, and SHALL reject replacement through its template build interface.

#### Scenario: Recreated template has the same VMID
- **WHEN** a clone plan references an earlier template record but the current object's native identity or bound disk/configuration facts differ
- **THEN** apply SHALL reject the reference before snippet upload or other facility mutation
- **AND** matching names, VMIDs or copied record identifiers alone SHALL NOT authorize cloning

#### Scenario: Publication was revoked
- **WHEN** a plan actually requires cloning and the caller's current admission is revoked, missing, inconsistent or unconfirmed
- **THEN** apply SHALL reject that dependency without choosing another version or using an old admission snapshot
- **AND** checks through clone completion SHALL require caller-maintained serialization with template lifecycle writes

#### Scenario: Independent full clone no longer needs its template
- **WHEN** an existing full clone is updated or deleted without a native action depending on the original template
- **THEN** template revocation alone SHALL NOT block that operation
- **AND** unknown native template dependencies SHALL NOT be silently treated as absent

#### Scenario: Published template replacement is requested
- **WHEN** a build requests an occupied VMID or force replacement
- **THEN** the supported helper and runtime SHALL refuse in-place replacement
- **AND** a new build SHALL use a distinct new version and VMID, with retirement separately authorized by the caller

### Requirement: Cleanup follows current management ownership
Template cleanup SHALL be an explicitly reviewed action bound to an original execution, exact objects, confirmed inactivity and current management ownership.

#### Scenario: Remove a failed helper-created object
- **WHEN** the selected object is evidenced as created by the helper execution, remains helper-managed, is not in OpenTofu state and its originating task is stopped
- **THEN** cleanup apply SHALL affect only the exact admitted object and confirmed associated volumes
- **AND** it SHALL return a separate cleanup execution result linked to the original execution

#### Scenario: Verification VM is OpenTofu-managed
- **WHEN** a temporary verification VM was created by or later imported into OpenTofu
- **THEN** helper cleanup SHALL reject direct deletion and direct the caller to an explicit deletion plan for the owning complete root
- **AND** recovery SHALL require device, declaration and state reconciliation rather than treating device deletion alone as resolved

#### Scenario: Retire a completed template
- **WHEN** cleanup targets a completed template rather than an incomplete build artifact
- **THEN** it SHALL additionally require the caller's current retirement authorization and dependency disposition bound to the exact object and cleanup preview
- **AND** published or revoked status alone SHALL NOT authorize deletion, and unresolved dependent clones SHALL block retirement
- **AND** helper-created provenance SHALL NOT override current OpenTofu ownership or permit deletion through ordinary failed-build recovery

#### Scenario: Management or activity is unknown
- **WHEN** current ownership, object association or remote inactivity cannot be confirmed
- **THEN** automated cleanup SHALL reject the object without scanning unrelated backends, guessing ownership from names or broadening the deletion set
- **AND** a caller's pending recovery context SHALL NOT authorize replay of the failed build
