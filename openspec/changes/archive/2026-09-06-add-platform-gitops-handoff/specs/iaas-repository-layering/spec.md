## MODIFIED Requirements

### Requirement: Repository layers express ownership
The repository SHALL separate Astra-specific configuration, reusable
automation, and the external platform-repository handoff boundary into explicit
top-level layers.

#### Scenario: Operator locates Astra environment data
- **WHEN** an operator reviews Astra inventory, Ansible data, runtime templates, generated deployment inputs, or the Astra OpenTofu root
- **THEN** those tracked environment artifacts SHALL be located under `environments/astra/`

#### Scenario: Developer locates reusable automation
- **WHEN** a developer changes Python automation, reusable Ansible workflows, OpenTofu modules, Packer mechanisms, or PVE-node automation
- **THEN** those implementations SHALL be located under `automation/`
- **AND** concrete Astra PVE topology and VM declarations SHALL remain outside reusable automation

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
