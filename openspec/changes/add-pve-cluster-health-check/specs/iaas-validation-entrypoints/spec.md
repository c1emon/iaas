## MODIFIED Requirements

### Requirement: Online and mutation workflows remain explicit
The system SHALL keep online checks, planning, and mutation-capable operations outside the default offline validation path.

#### Scenario: Preserve explicit online PVE checks
- **WHEN** operators need to validate live PVE readiness or health
- **THEN** they SHALL use explicit online targets or workflows separate from the aggregate offline check
- **AND** the default offline check SHALL NOT depend on PVE online preflight or PVE cluster health targets

#### Scenario: Preserve explicit planning and mutation operations
- **WHEN** operators need to run OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer template builds, Ansible mutation, PVE maintenance, VM migration, or node reboot workflows
- **THEN** those operations SHALL remain explicit commands
- **AND** they SHALL NOT be dependencies of the aggregate offline check
- **AND** they SHALL NOT run automatically in the initial cloud CI workflow

### Requirement: P0 hygiene checks remain offline and CI-compatible
The system SHALL keep newly added P0 hygiene checks compatible with cloud CI and disconnected developer workstations.

#### Scenario: CI runs P0 hygiene checks
- **WHEN** GitHub Actions or another CI platform runs P0 hygiene checks
- **THEN** it SHALL invoke repository-owned targets
- **AND** it SHALL NOT define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets
- **AND** it SHALL NOT run PVE preflight, PVE cluster health checks, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, PVE maintenance, or infrastructure mutation
