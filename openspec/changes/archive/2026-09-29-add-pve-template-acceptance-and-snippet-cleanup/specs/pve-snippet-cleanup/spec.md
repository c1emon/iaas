## ADDED Requirements

### Requirement: Cleanup consumes exact original VM ownership evidence
The runtime SHALL require an explicit evidence-bound origin of deployment or acceptance, original VM/execution identity, exact generation/upload records and confirmed VM deletion before deleting snippets. Deployment cleanup SHALL additionally retain the approved delete-plan and state-persistence associations; acceptance cleanup SHALL instead consume the original acceptance request/journal and create/delete authorization without inventing plan/state evidence.

#### Scenario: Cleanup valid original records
- **WHEN** records consistently bind the selected files to the deleted VM and its deployment/delete execution
- **THEN** the runtime SHALL independently confirm VM absence and restrict deletion to the exact original list
- **AND** it SHALL NOT infer ownership from filename prefixes, VMID alone, wildcard paths or caller assertions without associated evidence

#### Scenario: Cleanup a deleted acceptance VM's remaining snippets
- **WHEN** the original acceptance request/journal proves its temporary VM identity, authorization, exact snippet list and confirmed VM deletion
- **THEN** standalone cleanup SHALL accept that origin without plan/state evidence and SHALL apply the same ownership, reference, content, serialization and absence checks
- **AND** it SHALL NOT clone, delete the VM again, rewrite the acceptance result or accept an origin switch unsupported by the original materials

#### Scenario: VM still exists or records conflict
- **WHEN** the VMID is occupied, the original identity/evidence conflicts, or ownership is missing
- **THEN** the runtime SHALL refuse deletion and report the reason without deleting the VM or altering its state

### Requirement: Complete reference checks cover shared storage
The runtime SHALL hold the existing complete mutation serialization context and establish complete VM/template reference visibility for the relevant storage scope, including shared nodes and applicable pending/snapshot configurations, before concluding that a file is unreferenced.

#### Scenario: Another object references the snippet
- **WHEN** any relevant VM or template references the selected file, including through a shared storage scope
- **THEN** that file SHALL be retained and reported as referenced

#### Scenario: Reference scope cannot be established
- **WHEN** permissions are insufficient, a query fails, storage aliasing is unresolved or scope is incomplete
- **THEN** no absence-of-reference conclusion SHALL be made and affected files SHALL NOT be deleted
- **AND** an ACL-filtered empty inventory or local-node-only scan SHALL NOT stand in for complete visibility

### Requirement: Restricted deletion rechecks exact content
Snippet deletion SHALL use the established restricted execution and trust channels, validate exact file identity and original content digest immediately before deletion, and verify the resulting absence.

#### Scenario: File matches its original record
- **WHEN** ownership, reference scope, content digest, path safety and mutual exclusion checks pass
- **THEN** the helper SHALL delete only the listed regular file and return deleted only after confirming completion
- **AND** callers SHALL NOT need arbitrary SSH rm, shell commands or broad sudo rights

#### Scenario: File is already absent or changed
- **WHEN** a legitimate exact target is conclusively absent
- **THEN** that item SHALL return already_absent
- **AND** a present file with mismatched digest/ownership SHALL return mismatch without deletion; inaccessible files and unresolved paths SHALL NOT be treated as absent

### Requirement: Cleanup retries preserve original scope
The runtime SHALL allow a new admitted cleanup execution after failure, linked to the previous cleanup and original ownership list, without replaying the VM lifecycle. First standalone cleanup SHALL declare retry_of and retry_materials as null; retry SHALL provide the previous cleanup execution ID and protected request/journal/available-result references.

#### Scenario: Retry after partial cleanup
- **WHEN** the caller supplies the original list and associations with a new cleanup execution admission
- **THEN** the runtime SHALL validate retry_of, previous request digest, unchanged origin/target/VM/ownership/full-list associations and original mutation inactivity before rechecking all deletion predicates; already absent items SHALL complete idempotently and independently safe remaining items MAY be cleaned
- **AND** the runtime SHALL NOT add files, replace expected digests, delete the VM again, write state, force-unlock or change original results

#### Scenario: Retry evidence is invalid or incomplete
- **WHEN** retry_of refers to itself or another execution, core evidence is missing, the selected list differs or previous mutation activity remains unknown
- **THEN** the runtime SHALL refuse cleanup mutation and report the conflicting or unknown association
- **AND** a missing final result alone MAY be handled with an otherwise complete bound journal without fabricating original success

#### Scenario: Repeat the same cleanup execution ID
- **WHEN** an existing cleanup execution ID is resubmitted
- **THEN** the caller SHALL route it to observe with the read-only original execution directory; matching inputs SHALL only expose original observations, conflicts SHALL be refused and missing core material SHALL return unknown without PVE mutation

### Requirement: Cleanup returns per-file and residual outcomes
The runtime SHALL return versioned execution/origin/original-VM associations, the applicable delete-plan or acceptance-request digest, and per-file deleted, already_absent, referenced, mismatch, failed or unknown outcomes with bounded reasons and residual identities.

#### Scenario: Some files cannot be cleaned
- **WHEN** a reference, mismatch, check/delete failure or uncertain outcome affects any file
- **THEN** completed files SHALL retain their independent facts and the batch SHALL NOT report passed
- **AND** incomplete global visibility SHALL block batch mutation, and unknown residual existence SHALL remain explicit
