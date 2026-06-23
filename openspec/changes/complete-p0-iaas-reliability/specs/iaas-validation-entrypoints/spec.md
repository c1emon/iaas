## ADDED Requirements

### Requirement: Offline secret scanning entrypoint
The system SHALL expose a repository-owned offline secret scanning command for local operators and CI.

#### Scenario: Run secret scanning without infrastructure access
- **WHEN** an operator or CI runs the repository secret scanning command
- **THEN** the command SHALL scan repository files for committed secrets or credential-like material
- **AND** it SHALL NOT require PVE, OPNsense, switch, SSH, 1Password, or apply-capable credentials
- **AND** it SHALL NOT contact or mutate internal infrastructure

#### Scenario: Secret scanning finds suspicious committed material
- **WHEN** the secret scanning command detects unapproved secret-like content
- **THEN** the command SHALL fail
- **AND** it SHALL report enough file context for review without requiring secret disclosure in documentation or configuration

#### Scenario: Secret scanning needs an allowlist or baseline
- **WHEN** known safe placeholders, examples, checksums, or historical values would otherwise cause false positives
- **THEN** the repository SHALL keep scanner configuration, allowlist, or baseline data under reviewable source control
- **AND** the default behavior SHALL still fail on new unapproved findings

### Requirement: Explicit Ansible syntax validation entrypoint
The system SHALL keep Ansible syntax validation available as an explicit command without requiring it in the default offline aggregate check.

#### Scenario: Operator explicitly requests Ansible syntax validation
- **WHEN** an operator runs the explicit Ansible syntax validation target
- **THEN** the system SHALL run syntax validation for the intended repository Ansible playbooks or PVE guest verification playbooks
- **AND** it SHALL use repository-owned command targets rather than CI-only inline logic

#### Scenario: Operator or CI runs default aggregate validation
- **WHEN** the default aggregate offline check runs
- **THEN** Ansible syntax validation SHALL NOT be required as part of that default gate in this P0 closure change
- **AND** online guest reachability, SSH ping, and mutation playbooks SHALL remain outside the default gate

### Requirement: P0 hygiene checks remain offline and CI-compatible
The system SHALL keep newly added P0 hygiene checks compatible with cloud CI and disconnected developer workstations.

#### Scenario: CI runs P0 hygiene checks
- **WHEN** GitHub Actions or another CI platform runs P0 hygiene checks
- **THEN** it SHALL invoke repository-owned targets
- **AND** it SHALL NOT define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets
- **AND** it SHALL NOT run PVE preflight, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, or infrastructure mutation

#### Scenario: Validation documentation lists available local checks
- **WHEN** an operator reads the local validation documentation
- **THEN** it SHALL distinguish default offline checks from optional explicit hygiene checks
- **AND** it SHALL identify which commands are safe anywhere and which commands require explicit online/runtime context
