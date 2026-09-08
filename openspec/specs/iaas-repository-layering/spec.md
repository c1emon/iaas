# iaas-repository-layering Specification

## Purpose
Define the ownership boundaries and hard-cutover contract that separate selected environment configuration, reusable infrastructure automation, and the external platform-repository handoff boundary.

## Requirements

### Requirement: Repository layers express ownership
The repository SHALL separate named environment configuration, reusable
automation, and the external platform-repository handoff boundary into explicit
ownership layers. Generic execution SHALL select an environment explicitly.

#### Scenario: Operator locates actual environment data
- **WHEN** an operator reviews actual inventory, Ansible data, runtime templates, generated deployment inputs, or an OpenTofu root
- **THEN** those artifacts SHALL be maintained in a caller-owned repository outside this runtime checkout
- **AND** actual topology, host identities, domains, state and operational evidence SHALL NOT be runtime source or CI fixtures

#### Scenario: Developer locates reusable automation
- **WHEN** a developer changes Python automation, reusable Ansible workflows, OpenTofu modules, Packer mechanisms, or PVE-node automation
- **THEN** those implementations SHALL be located under `automation/`
- **AND** concrete environment PVE topology and VM declarations SHALL remain outside reusable automation

#### Scenario: Operator supplies an independent environment repository
- **WHEN** an operator selects a local or external environment directory explicitly
- **THEN** reusable automation SHALL consume that environment through the same generic path interface
- **AND** environment-specific inventories, policy and OpenTofu roots SHALL remain owned by that environment
- **AND** valuable existing environment material SHALL be preserved in the caller-owned location during separation
- **AND** repository tests and CI SHALL use synthetic fixtures without live credentials or infrastructure access

### Requirement: PVE and VM inventories are authoritative
The repository SHALL use the explicitly selected environment's PVE cluster and VM inventories as the authoritative declarations for PVE topology and VM lifecycle facts.

#### Scenario: PVE or VM facts are consumed
- **WHEN** validation, rendering, health expectations, preflight expectations, or deployment inputs require PVE topology or VM lifecycle facts
- **THEN** they SHALL derive those facts from the selected environment's `inventory/pve-cluster.yml` and `inventory/vms.yml`, or explicitly supplied equivalent input files
- **AND** reusable validation, rendering, and expectation code SHALL NOT require matching concrete environment constants
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
The runtime SHALL NOT silently discard, migrate or initialize caller-owned state when environment files are relocated.

#### Scenario: Environment material is relocated outside the runtime repository
- **WHEN** actual environment files and local operational material are moved to caller-owned storage
- **THEN** existing state and backup files SHALL be preserved with their access restrictions
- **AND** the file relocation SHALL NOT be represented as a backend migration or successful infrastructure operation
- **AND** the caller SHALL review backend and module initialization before subsequent plan or apply

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

The repository SHALL keep shared in-cluster platform desired state outside this
IaaS repository and SHALL use `platform/` only to document the external
platform repository handoff boundary.

#### Scenario: Operator inspects the platform boundary

- **WHEN** the platform handoff capability is implemented
- **THEN** `platform/README.md` SHALL describe the external platform repository as the owner of Flux and shared in-cluster services
- **AND** ordinary application release content SHALL remain owned by application repositories
- **AND** `platform/` SHALL NOT contain Flux, Cilium, CSI, Gateway, certificate, observability, application manifests, Helm releases, reconciliation roots, or production runtime configuration
- **AND** reusable VM and K3s lifecycle automation SHALL remain under `automation/`
