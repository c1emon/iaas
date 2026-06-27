## ADDED Requirements

### Requirement: Validation CLI failures are operator-readable
The system SHALL convert expected repository validation failures at CLI boundaries into stable operator-readable errors.

#### Scenario: PVE inventory CLI receives invalid operator-authored input
- **WHEN** a PVE inventory CLI command fails because source-of-truth input is invalid
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material

#### Scenario: Services inventory CLI receives invalid operator-authored input
- **WHEN** a services inventory CLI command fails because source-of-truth input is invalid
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material

## MODIFIED Requirements

### Requirement: P0 hygiene checks remain offline and CI-compatible
The system SHALL keep newly added P0 hygiene checks compatible with cloud CI and disconnected developer workstations.

#### Scenario: CI runs P0 hygiene checks
- **WHEN** GitHub Actions or another CI platform runs P0 hygiene checks
- **THEN** it SHALL invoke repository-owned targets
- **AND** it SHALL NOT define or require PVE, OPNsense, switch, 1Password, SSH, or apply-capable secrets
- **AND** it SHALL NOT run PVE preflight, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, or infrastructure mutation

#### Scenario: Runtime state artifacts are accidentally tracked
- **WHEN** local OpenTofu state, provider directories, virtual environments, caches, Ansible collections, or platform metadata files are accidentally added to source control
- **THEN** repository hygiene checks or reviewable repository rules SHALL reject or clearly surface the tracked runtime artifact
- **AND** the default offline check SHALL NOT delete ignored local runtime artifacts automatically
