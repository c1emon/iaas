## Purpose

Define consistent management of destination and one-to-one NAT while preserving native differences, explicit resource ownership, backward compatibility and caller control over site policy and migration. Source NAT naming remains reserved for a later change and is not an active capability here.

## ADDED Requirements

### Requirement: Unified lifecycle with independent resources
The system SHALL expose independent dnat and one-to-one-nat resource selections, files and validators with common identity, admission and lifecycle conventions. It SHALL NOT accept fields belonging only to another NAT type or infer resource type from a mixed universal record. Existing four-resource callers SHALL remain valid without new files. `snat`, `snat.yml`, `opnsense_snat_rules`, `manage-snat.yml` and `opnsense_snat_source` SHALL remain unregistered deferred names until a later upstream compatibility change.

#### Scenario: Resource-specific field is misplaced
- **WHEN** a one-to-one record includes a DNAT associated_rule or destination port
- **THEN** local validation rejects the record instead of ignoring the field or selecting another provider

#### Scenario: Resource not selected
- **WHEN** a caller has not selected a NAT resource
- **THEN** that resource is not required, discovered or managed

### Requirement: Stable identity and additive ownership
Each active NAT resource SHALL derive its unique description from its type, scope and slug as iaas:opnsense:<type>:<scope>:<slug>. Present SHALL create/update/enable/disable its object, absent SHALL delete only its exact object, and omission SHALL preserve appliance objects. Ambiguous live matches and duplicate identities within a type SHALL fail. No site addresses, ownership inference or namespace-wide cleanup SHALL be embedded.

#### Scenario: Separate NAT identity domains
- **WHEN** DNAT and one-to-one NAT declarations share scope and slug
- **THEN** their type-specific descriptions identify distinct objects

#### Scenario: Explicit absent declaration
- **WHEN** an absent record contains only its identity and state
- **THEN** deletion does not require former target/port fields and does not affect an undeclared object

### Requirement: Per-resource activation and honest recovery
NAT CRUD SHALL suppress per-item reload. A successful changed single-resource batch SHALL activate once using its verified native target; check mode SHALL never activate. CRUD failure SHALL stop activation and report possibly saved partial changes. Activation failure SHALL distinguish saved/running state. An explicit strict boolean force-reload option SHALL permit unchanged recovery. Cross-resource atomicity, automatically chosen deployment order and isolated appliance-wide reload effects SHALL NOT be claimed.

#### Scenario: A later resource batch fails
- **WHEN** the caller's earlier batch succeeded but a later batch fails
- **THEN** the failure is reported without claiming rollback of the earlier batch or automatically continuing migration

#### Scenario: Read-only check mode
- **WHEN** a resource runs in check mode
- **THEN** it performs no CRUD or activation, including when force reload is requested

### Requirement: Complete declarations for managed optional fields
Present records SHALL fully declare the supported managed fields. Omitted optional fields SHALL reset to their documented defaults or clear values rather than preserve stale configuration through provider omission. Optional port constraints, translation ports and tags SHALL clear; optional inversion and logging flags SHALL default false. Unmanaged native fields and undeclared objects SHALL remain untouched. Adapters SHALL verify the fixed provider's effective clear encoding.

#### Scenario: Translation port is removed
- **WHEN** a DNAT rule previously configured local_port and its new declaration omits local_port
- **THEN** the old translation port is cleared, the packet's original destination port is used and repeating the declaration is unchanged

### Requirement: Unsupported live exception modes are not silently converted
The initial present contract SHALL manage ordinary DNAT with native `nordr=false` (provider-normalized as `no_port_forward=false`). After local and credential admission, provider-backed read-only lookup SHALL check the exact matched DNAT object before the resource batch's first write. A matched present object's `nordr` enabled or indeterminate exception mode SHALL reject the batch instead of relying on a provider default that silently converts it. Undeclared objects SHALL remain unaffected. Explicit absent SHALL still permit identity-based deletion without requiring the former translation fields. One-to-one NAT SHALL not accept or infer this DNAT exception field.

#### Scenario: Managed identity matches an exemption rule
- **WHEN** a present DNAT declaration matches a live object with `nordr` true
- **THEN** the resource batch fails before any write without changing the exemption into ordinary port forwarding

### Requirement: Offline generation and explicit Ansible execution
Runtime integration SHALL add only optional check/generate inputs; it SHALL NOT introduce an OPNsense launcher apply operation. Device writes SHALL use the respective manage-dnat.yml or manage-one-to-one-nat.yml playbook with caller inventory and explicit target limit. Source variables SHALL default to the selected environment's standard files and accept explicit generated-file paths. Each playbook SHALL validate the selected file and revalidate the actual loaded list before credential preflight. SNAT's reserved manage-snat.yml/opnsense_snat_source names SHALL remain unavailable in this change.

#### Scenario: Generated resource is handed to a playbook
- **WHEN** the caller selects a generated NAT file through the resource's source variable
- **THEN** the playbook validates and loads that file and validates any precedence-adjusted list before credentials; generation alone performs no device operation

### Requirement: Generic resources do not own shared modes or site composition
The system SHALL NOT change global reflection settings or outbound NAT automatic/hybrid/manual mode, synthesize a site hairpin configuration, create a proxy policy or manage nginx/DNS. Callers SHALL explicitly supply the standard resources and arrange their deployment. Fixed provider loading and representative compatibility/regression tests SHALL precede software support claims; runtime execution SHALL NOT fetch dependencies.

#### Scenario: Caller needs hairpin NAT
- **WHEN** hairpin behavior requires DNAT, one-to-one NAT and filtering declarations
- **THEN** each provided active resource is managed through its own contract and missing site configuration is not inferred; any SNAT requirement remains deferred

#### Scenario: Provider behavior is incompatible
- **WHEN** the fixed provider cannot satisfy a declared resource contract
- **THEN** that resource cannot be marked complete merely because another NAT type passed
