## REMOVED Requirements

### Requirement: Independent fixed template preview
**Reason**: The combined image-building preview is replaced by publication-only inputs.
**Migration**: Use image build separately, then prepare a new publication preview; no old input translation.

### Requirement: Durable remotely queryable template execution
**Reason**: The node systemd build worker is replaced by a caller-local journal and native HTTPS tasks.
**Migration**: Drain old tasks and retain original evidence before removing worker assets; all new operations use the publisher.

### Requirement: Template facts and publication are separate
**Reason**: Build facts now arrive through an independent artifact and PVE publication remains separate from caller promotion.
**Migration**: Adopt new result/record schemas directly without converting historical build evidence.

### Requirement: Template references identify the current object
**Reason**: Template dependencies now consume new publication/observation records directly.
**Migration**: Create fresh records and plans; preserve native identity checks and current caller admission.

### Requirement: Cleanup follows current management ownership
**Reason**: Cleanup ownership moves from node helper to external publisher, with separate local image cleanup.
**Migration**: Preserve current ownership/inactivity/retirement safeguards using new action-specific inputs; never replay old cleanup previews.

## ADDED Requirements

### Requirement: Independent fixed image publication preview
The system SHALL expose check/read/plan/apply/verify for publication of an existing image, independently of image building, VM declarations and OpenTofu state, using the new image publication contract.

#### Scenario: Plan and publish an existing image
- **WHEN** a caller selects an image-artifact/v1, exact source object, runtime, target, stores, hardware and free VMID
- **THEN** plan SHALL bind those inputs into pve-template-preview/v2 without downloading/uploading the disk or changing PVE
- **AND** apply SHALL require the exact association, current caller execution admission and serialization, and SHALL never build or customize the image
- **AND** the runtime SHALL recheck full-authority VM inventory, API permissions, storage capability/enabled/active state, node visibility, bridge, firmware and known capacity/size constraints before dependent writes
- **AND** known insufficient publisher-local or API-visible storage capacity SHALL block dependent writes

#### Scenario: Transfer a private image
- **WHEN** publication consumes a private artifact source
- **THEN** the runtime SHALL download and verify it locally before official HTTPS multipart upload to import storage
- **AND** it SHALL NOT pass secret URLs to PVE download-url or use CLI writes as a fallback
- **AND** unique staging names, preexisting-file refusal and scoped upload/delete permissions SHALL prevent overwriting or adopting unrelated import files
- **AND** capacity checks SHALL use publisher-local and API-visible storage information and account for known shared filesystem usage

#### Scenario: Receiving-node details are not observable
- **WHEN** exact receiving-node /var/tmp capacity or proxy upload limits cannot be observed through the available interface
- **THEN** the publisher SHALL report that limitation and apply explicit site constraints where provided, without treating another storage's capacity as equivalent evidence
- **AND** absence of that exact observation alone SHALL NOT require SSH, a new space helper or block publication
- **AND** actual ENOSPC, upload-limit rejection and uncertain request outcomes SHALL retain their normal failure and recovery semantics

### Requirement: Durable HTTPS publication execution
The publisher SHALL retain a private execution journal outside an ephemeral runtime and correlate native PVE tasks before advancing dependent phases, without requiring a node build worker.

#### Scenario: Controller disconnects or loses a response
- **WHEN** a PVE mutation may have been accepted but its response or completion is unknown
- **THEN** read SHALL observe the original journal, uniquely associated tasks and exact objects without replaying the request
- **AND** effects SHALL remain unknown where acceptance/completion cannot be proved, even if current configuration matches
- **AND** caller pending and the original evidence SHALL remain available for a separately admitted recovery

#### Scenario: Concurrent publication or cleanup
- **WHEN** operations share a target or staging protection domain
- **THEN** caller serialization SHALL cover admission, mutation, task completion and cleanup, and apply SHALL recheck mutable facts under that context
- **AND** matching duplicate execution IDs SHALL query only, conflicting inputs SHALL fail, and task observation SHALL not require holding a long mutation lock

#### Scenario: Recover task evidence
- **WHEN** a subsequent caller reads a retained execution with appropriate task-read permissions
- **THEN** the result SHALL preserve phase intent, received UPIDs, native outcomes, known objects and missing conclusions
- **AND** object presence, stale running records and template flags SHALL NOT prove historical success or current activity

### Requirement: Publication facts and caller promotion are separate
The system SHALL report technical PVE publication facts separately from image construction, guest checks and caller-owned availability/promotion.

#### Scenario: Deliver a technically published template
- **WHEN** native conversion finishes successfully
- **THEN** the publisher SHALL additionally verify exact object identity, associated volumes, template flag and required hardware/Cloud-init configuration
- **AND** it SHALL return pve-template-record/v2 linked to the artifact and execution without declaring caller promotion or unperformed guest acceptance
- **AND** required template verification or result collection failure SHALL prevent overall success while preserving independently confirmed template facts

#### Scenario: Only known staging cleanup remains
- **WHEN** template verification succeeds, all original native tasks are confirmed stopped, results are durably retained and the only remaining effect is an exact publisher-owned staging file whose deletion failed
- **THEN** publication MAY succeed with an explicit cleanup warning and separately retained cleanup-failed status
- **AND** the caller MAY settle the original publication pending and evaluate template availability under its normal policy while tracking cleanup independently
- **AND** subsequent staging deletion SHALL still require a new PVE cleanup plan/apply with current ownership and task-inactivity checks
- **AND** unknown activity, ownership, object effects or required result persistence SHALL NOT be reclassified as this known-residual case

#### Scenario: Observe a pre-existing template
- **WHEN** a caller selects a current template directly
- **THEN** read SHALL create a fresh new-schema observation of its exact identity/configuration
- **AND** it SHALL NOT parse/upgrade an old record or invent historical image cleaning, build or execution success

#### Scenario: Validate before promotion
- **WHEN** a caller admits a new template only for a bounded verification VM
- **THEN** it SHALL be usable only for that verification purpose until the caller supplies current normal-use admission

### Requirement: Published template references identify current objects
The system SHALL bind new-schema template records and VM dependencies to current native identities beyond node/VMID and SHALL prohibit replacement via publication.

#### Scenario: Reused VMID or revoked version
- **WHEN** actual UUID, volume/configuration association or current caller admission differs from the bound dependency
- **THEN** VM apply SHALL reject before snippet upload or other facility writes without translating a legacy record or choosing another template
- **AND** missing identity/dependency evidence SHALL fail closed

#### Scenario: Independent full clone
- **WHEN** an existing full clone is updated/deleted without native dependence on its original template
- **THEN** template revocation alone SHALL NOT block the action
- **AND** unknown dependencies SHALL NOT be interpreted as independence

#### Scenario: Occupied VMID
- **WHEN** publication selects an occupied VMID or requests force replacement
- **THEN** it SHALL reject without modifying that object
- **AND** new versions SHALL use new identities with retirement separately admitted

### Requirement: Publication cleanup follows current management ownership
Cleanup and retirement SHALL consume explicit action-specific requests/previews and current caller admission, and SHALL only delete exact resources whose current ownership and inactivity are confirmed.

#### Scenario: Clean an incomplete publication
- **WHEN** the original publication tasks are confirmed stopped and the selected objects/import files remain publisher-owned
- **THEN** a new cleanup execution linked by recovery_of SHALL delete only the admitted set after rechecking associations
- **AND** unknown-ownership files, PVE internal upload temp files and unrelated cached objects SHALL NOT be swept

#### Scenario: Ownership moved or is unknown
- **WHEN** a VM is OpenTofu-managed or ownership/activity cannot be established
- **THEN** publisher cleanup SHALL reject deletion and retain evidence for the owning root or caller reconciliation
- **AND** the original pending context SHALL NOT authorize replay

#### Scenario: Retire a complete template
- **WHEN** a complete template is selected
- **THEN** action=retire SHALL require its new record, current retirement/dependency admission and independently checked observable facts
- **AND** unresolved dependent clones SHALL block deletion while independent full clones SHALL NOT
- **AND** failed-publication cleanup, revoked status or creation provenance alone SHALL NOT authorize retirement or S3 artifact deletion
