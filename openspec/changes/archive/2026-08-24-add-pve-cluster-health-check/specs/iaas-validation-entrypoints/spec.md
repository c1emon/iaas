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

#### Scenario: Keep Ansible syntax-check explicit in P0
- **WHEN** the P0 aggregate offline check is implemented
- **THEN** Ansible syntax-check SHALL NOT be required as part of the default aggregate check
- **AND** any Ansible syntax-check target SHALL remain explicit until a later change promotes it into the default gate

#### Scenario: Defer internal CI trigger paths
- **WHEN** operators want tag-triggered Forgejo/Woodpecker-style internal CI
- **THEN** that behavior SHALL be handled by a later change
- **AND** this change SHALL only provide a command surface that such a later CI path can call

### Requirement: P0 hygiene checks remain offline and CI-compatible
The system SHALL keep newly added P0 hygiene checks compatible with cloud CI and disconnected developer workstations.

#### Scenario: CI runs P0 hygiene checks
- **WHEN** GitHub Actions or another CI platform runs P0 hygiene checks
- **THEN** it SHALL invoke repository-owned targets
- **AND** it SHALL NOT define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets
- **AND** it SHALL NOT run PVE preflight, PVE cluster health checks, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, PVE maintenance, or infrastructure mutation

#### Scenario: Runtime state artifacts are accidentally tracked
- **WHEN** local OpenTofu state, provider directories, virtual environments, caches, Ansible collections, or platform metadata files are accidentally added to source control
- **THEN** repository hygiene checks or reviewable repository rules SHALL reject or clearly surface the tracked runtime artifact as a failure
- **AND** the default offline check SHALL NOT delete ignored local runtime artifacts automatically

#### Scenario: Validation documentation lists available local checks
- **WHEN** an operator reads the local validation documentation
- **THEN** it SHALL distinguish default offline checks from optional explicit hygiene checks
- **AND** it SHALL identify which commands are safe anywhere and which commands require explicit online/runtime context
