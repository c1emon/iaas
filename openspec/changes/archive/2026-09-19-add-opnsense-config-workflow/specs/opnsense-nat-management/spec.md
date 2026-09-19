## MODIFIED Requirements

### Requirement: Unified lifecycle with independent resources
The system SHALL expose independent dnat and one-to-one-nat resource selections, files and validators with common identity, admission and lifecycle conventions. It SHALL NOT accept fields belonging only to another NAT type or infer resource type from a mixed universal record. Existing four-resource callers SHALL remain valid without new files. `snat`, `snat.yml`, `opnsense_snat_rules`, `manage-snat.yml` and `opnsense_snat_source` SHALL remain unregistered deferred names until a later upstream compatibility change. The explicit online configuration workflow SHALL be permitted to read necessary references in unselected resources without enrolling them as desired inputs or mutations.

#### Scenario: Resource-specific field is misplaced
- **WHEN** a one-to-one record includes a DNAT associated_rule or destination port
- **THEN** local validation rejects the record instead of ignoring the field or selecting another provider

#### Scenario: Resource not selected
- **WHEN** a caller has not selected a NAT resource
- **THEN** its desired file is not required or automatically discovered and its objects are not managed
- **AND** only necessary read-only dependency checks in an explicit online configuration workflow may inspect relevant unselected live NAT references

### Requirement: Per-resource activation and honest recovery
NAT CRUD SHALL suppress per-item reload. A successful changed single-resource batch SHALL activate once using its verified native target; check mode SHALL never activate. CRUD failure SHALL stop activation and report possibly saved partial changes. Activation failure SHALL distinguish saved/running state. An explicit strict boolean force-reload option SHALL permit unchanged recovery in direct execution. The generic configuration workflow SHALL be permitted to order explicitly selected resource stages by supported references, with each actual stage satisfying activation dependencies and shared reload admission. It SHALL NOT choose site migration stages, add unselected mutations or claim cross-resource atomicity or isolated appliance-wide reload effects.

#### Scenario: A later resource batch fails
- **WHEN** the caller's earlier batch succeeded but a later batch fails
- **THEN** the failure is reported without claiming rollback of the earlier batch or automatically continuing migration

#### Scenario: Read-only check mode
- **WHEN** a resource runs in check mode
- **THEN** it performs no CRUD or activation, including when force reload is requested

#### Scenario: Generic reference ordering
- **WHEN** a reviewed configuration candidate explicitly selects prerequisite creation, NAT reference changes and prerequisite retirement
- **THEN** the workflow orders those resource stages while leaving business migration sequencing to the caller
- **AND** it refuses missing necessary selections instead of extending the write set

### Requirement: Offline generation and explicit Ansible execution
Runtime integration SHALL retain optional offline check/generate inputs and SHALL support the explicit OPNsense configuration workflow for reviewed online plan/apply/verify and resource reads. Device writes SHALL reuse the respective manage-dnat.yml or manage-one-to-one-nat.yml resource implementation, with an exact target selected by the launcher or caller inventory and explicit limit for direct Ansible invocation. Source variables SHALL default to the selected environment's standard files for direct execution and accept explicit generated-file paths. Each execution SHALL validate the selected file and revalidate the actual loaded list before credential preflight. Generation SHALL NOT trigger device execution. SNAT's reserved manage-snat.yml/opnsense_snat_source names SHALL remain unavailable.

#### Scenario: Generated resource is handed to a playbook
- **WHEN** the caller selects a generated NAT file through the resource's source variable
- **THEN** the playbook validates and loads that file and validates any precedence-adjusted list before credentials; generation alone performs no device operation

#### Scenario: Reviewed NAT candidate is applied through the launcher
- **WHEN** the caller explicitly invokes configuration workflow apply with selected NAT identities
- **THEN** the workflow performs candidate and live-state admission and reuses the resource implementation only for those selected identities
- **AND** direct Ansible source selection remains available without introducing native OpenTofu plan semantics
