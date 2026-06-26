## MODIFIED Requirements

### Requirement: Online and mutation workflows remain explicit
The system SHALL keep online checks, planning, and mutation-capable operations outside the default offline validation path.

#### Scenario: Preserve explicit planning and mutation operations
- **WHEN** operators need to run OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer template builds, Ansible mutation, PVE maintenance, VM migration, package updates, node reboot workflows, or Ceph mutation
- **THEN** those operations SHALL remain explicit commands or manual runbook steps
- **AND** they SHALL NOT be dependencies of the aggregate offline check
- **AND** they SHALL NOT run automatically in the initial cloud CI workflow

### Requirement: P0 hygiene checks remain offline and CI-compatible
The system SHALL keep newly added P0 hygiene checks compatible with cloud CI and disconnected developer workstations.

#### Scenario: CI runs P0 hygiene checks
- **WHEN** GitHub Actions or another CI platform runs P0 hygiene checks
- **THEN** it SHALL invoke repository-owned targets
- **AND** it SHALL NOT define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets
- **AND** it SHALL NOT run PVE preflight, PVE cluster health checks, PVE rolling maintenance, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, or infrastructure mutation
