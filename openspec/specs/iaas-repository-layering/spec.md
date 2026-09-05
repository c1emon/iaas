# iaas-repository-layering Specification

## Purpose
Define the ownership boundaries and hard-cutover contract that separate Astra environment configuration, reusable infrastructure automation, and the in-cluster platform ownership boundary.

## Requirements

### Requirement: Repository layers express ownership
The repository SHALL separate Astra-specific configuration, reusable automation, and future platform work into explicit top-level layers.

#### Scenario: Operator locates Astra environment data
- **WHEN** an operator reviews Astra inventory, Ansible data, runtime templates, generated deployment inputs, or the Astra OpenTofu root
- **THEN** those tracked environment artifacts SHALL be located under `environments/astra/`

#### Scenario: Developer locates reusable automation
- **WHEN** a developer changes Python automation, reusable Ansible workflows, OpenTofu modules, Packer mechanisms, or PVE-node automation
- **THEN** those implementations SHALL be located under `automation/`
- **AND** concrete Astra PVE topology and VM declarations SHALL remain outside reusable automation

### Requirement: PVE and VM inventories are authoritative
The repository SHALL use the Astra PVE cluster and VM inventories as the authoritative declarations for PVE topology and VM lifecycle facts.

#### Scenario: PVE or VM facts are consumed
- **WHEN** validation, rendering, health expectations, preflight expectations, or deployment inputs require PVE topology or VM lifecycle facts
- **THEN** they SHALL derive those facts from `environments/astra/inventory/pve-cluster.yml` and `environments/astra/inventory/vms.yml`
- **AND** reusable validation, rendering, and expectation code SHALL NOT require matching concrete Astra constants
- **AND** existing host-side wrapper protection envelopes MAY remain independent safety limits

#### Scenario: Invalid inventory relationships are declared
- **WHEN** inventory contains malformed, duplicate, unknown, contradictory, unsafe, or out-of-range relationships
- **THEN** validation SHALL fail before generation, online access, planning, or mutation
- **AND** structural, reference, network, provider-limit, lifecycle, and secret-safety checks SHALL remain in force

#### Scenario: Other environment data is authored
- **WHEN** service, foundation, Ansible, OPNsense, or switch data is not a PVE topology or VM lifecycle fact
- **THEN** it MAY remain authored in its existing domain-specific environment file
- **AND** this change SHALL NOT require every repeated repository value to be generated from one global source

### Requirement: Layer migration is a hard cutover
The repository SHALL update supported callers to the new layout without retaining compatibility paths.

#### Scenario: Migration completes
- **WHEN** the layering change is implemented
- **THEN** old supported source, automation, generated-output, package, and configuration paths SHALL be removed
- **AND** the repository SHALL NOT retain wrappers, import aliases, Make aliases, duplicate files, or symlinks whose purpose is to preserve the moved paths or `scripts.*` package surface
- **AND** current code, CI, tests, documentation, contracts, and operator commands SHALL reference the new paths

#### Scenario: Historical material contains an old path
- **WHEN** an archived OpenSpec change or clearly historical document records its original path
- **THEN** it MAY retain that path
- **AND** it SHALL NOT be treated as a current operator entrypoint

### Requirement: Legacy state is not migrated during cutover
The repository SHALL start the relocated OpenTofu root without migrating legacy state or backups.

#### Scenario: OpenTofu root is relocated
- **WHEN** the Astra OpenTofu root moves to `environments/astra/opentofu/pve/`
- **THEN** state files in the old OpenTofu root SHALL be discarded rather than copied into the relocated root
- **AND** existing ignored backup caches SHALL remain untouched and SHALL NOT be used by the relocated root
- **AND** the relocated root SHALL start without migrated state
- **AND** no state-migration or recovery gate SHALL be required as cutover evidence

### Requirement: Safety classes survive reorganization
Repository reorganization SHALL preserve the existing distinction among offline-safe, online read-only, and mutation-capable operations.

#### Scenario: Aggregate offline gate runs after migration
- **WHEN** an operator or CI runs the aggregate offline gate
- **THEN** it SHALL require no live infrastructure credentials or access
- **AND** it SHALL NOT generate runtime material, perform online reads, plan, or mutate infrastructure

#### Scenario: Operation with writes or live access is invoked
- **WHEN** an operator invokes generation, rendering, an online read, planning, or mutation
- **THEN** the canonical root command SHALL retain its existing safety class and documented side effects
- **AND** online and mutation-capable operations SHALL remain outside the aggregate offline gate

### Requirement: Platform remains an unimplemented boundary
The repository SHALL reserve `platform/` for future reusable in-cluster automation without claiming cluster capability in this change.

#### Scenario: Operator inspects the platform boundary
- **WHEN** the repository layering change is complete
- **THEN** `platform/README.md` SHALL describe the future boundary as planned and unimplemented
- **AND** no K3s, Cilium, Flux, CSI, Gateway, or application deployment implementation or completion claim SHALL be introduced
