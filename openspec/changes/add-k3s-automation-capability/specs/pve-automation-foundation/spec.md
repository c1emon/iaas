## ADDED Requirements

### Requirement: Template-derived VM architecture fact
The system SHALL treat guest CPU architecture as a generic VM/template fact and
SHALL NOT require workload overlays to restate it. The first implementation
SHALL support canonical `amd64`.

#### Scenario: VM inventory is normalized and rendered
- **WHEN** a VM references a template declaring canonical `amd64`
- **THEN** the normalized VM SHALL inherit that canonical template architecture
- **AND** generated Ansible host variables SHALL expose it as `pve_architecture`
- **AND** existing generated host facts and PVE lifecycle meanings SHALL remain unchanged

#### Scenario: Template architecture is invalid
- **WHEN** a referenced template omits architecture, uses a runtime alias such as `x86_64`, or declares another unsupported value
- **THEN** PVE inventory validation SHALL fail before OpenTofu, Ansible, documentation, or Packer outputs are accepted

#### Scenario: Workload consumes VM architecture
- **WHEN** K3s or another workload composes its intent with generated VM facts
- **THEN** it SHALL select architecture-specific behavior from `pve_architecture`
- **AND** it SHALL reject any workload-level per-node architecture override
