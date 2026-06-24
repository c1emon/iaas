# iaas-validation-entrypoints Specification

## Purpose
Define the repository-owned offline validation command surface used by local
operators and CI, while keeping online infrastructure checks, planning, and
mutation-capable operations explicit.

## Requirements
### Requirement: Root offline validation command surface
The system SHALL expose root-level commands for routine offline validation that can be run by both local operators and CI.

#### Scenario: Generate committed outputs from source inventory
- **WHEN** an operator runs the root generation command
- **THEN** the system SHALL regenerate committed non-sensitive outputs from operator-authored source-of-truth files
- **AND** it SHALL use the same generator behavior as the PVE inventory workflow
- **AND** it SHALL NOT require PVE API connectivity or runtime secrets

#### Scenario: Detect stale generated outputs
- **WHEN** source-of-truth inventory changes without updating committed generated outputs
- **THEN** the root generated-output check SHALL fail
- **AND** it SHALL report that generated files are stale
- **AND** it SHALL NOT modify files while running in check mode

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only offline-safe validation targets
- **AND** it SHALL include stale generated output detection
- **AND** it SHALL include relevant Python tests
- **AND** it SHALL include YAML linting for source-of-truth files
- **AND** it SHALL include OpenTofu formatting and offline validation where practical
- **AND** it SHALL NOT perform online infrastructure access or mutation

### Requirement: Offline checks require no internal infrastructure access
The default validation path SHALL be safe to run on a cloud CI runner or disconnected developer workstation.

#### Scenario: Run checks without PVE access
- **WHEN** the aggregate offline check runs in an environment with no PVE API route or credentials
- **THEN** the check SHALL still be able to complete successfully for a valid repository state
- **AND** it SHALL NOT attempt to read or modify PVE nodes, VMs, storage, bridges, templates, PCI mappings, or snippets

#### Scenario: Run checks without network automation access
- **WHEN** the aggregate offline check runs without OPNsense or switch credentials
- **THEN** the check SHALL NOT attempt to read or modify OPNsense configuration
- **AND** it SHALL NOT attempt to read or modify switch configuration

#### Scenario: Run checks without runtime secrets
- **WHEN** the aggregate offline check runs without 1Password, SSH agent, API token, or VM user secrets
- **THEN** the check SHALL not require those secrets
- **AND** generated outputs and logs SHALL NOT contain passwords, password hashes, private keys, API token secrets, or other runtime secrets

### Requirement: CI validates and reports only
The system SHALL provide an initial CI workflow that runs offline validation without internal infrastructure privileges.

#### Scenario: Validate a pull request in cloud CI
- **WHEN** a pull request triggers the CI workflow
- **THEN** GitHub Actions SHALL install the required validation toolchain
- **AND** it SHALL call repository-owned offline validation commands
- **AND** it SHALL report success or failure to the Git provider
- **AND** it SHALL NOT require internal network routes or infrastructure secrets

#### Scenario: Validate main branch updates in cloud CI
- **WHEN** changes are pushed to the main branch
- **THEN** CI SHALL run the same offline validation gate used for pull requests
- **AND** it SHALL NOT perform PVE preflight, OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer build, or Ansible mutation

#### Scenario: Keep CI platform replaceable
- **WHEN** the repository is validated by a different CI platform in the future
- **THEN** that CI platform SHALL be able to invoke the same repository-owned offline commands
- **AND** validation semantics SHALL NOT depend on GitHub Actions-specific behavior

#### Scenario: Defer secret scanning from first CI implementation
- **WHEN** the first P0 CI workflow is implemented
- **THEN** it SHALL NOT be required to run `gitleaks`, `trufflehog`, or another secret scanner
- **AND** secret scanning SHALL be left to a later change after the baseline and false-positive strategy are reviewed

### Requirement: Online and mutation workflows remain explicit
The system SHALL keep online checks, planning, and mutation-capable operations outside the default offline validation path.

#### Scenario: Preserve explicit online PVE checks
- **WHEN** operators need to validate live PVE state
- **THEN** they SHALL use an explicit online target or workflow separate from the aggregate offline check
- **AND** the default offline check SHALL NOT depend on that online target

#### Scenario: Preserve explicit planning and mutation operations
- **WHEN** operators need to run OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer template builds, or Ansible mutation
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

### Requirement: Explicit online PVE preflight remains outside offline validation
The system SHALL expose PVE online preflight as an explicit credentialed operation separate from default offline validation.

#### Scenario: Operator requests PVE online readiness checks
- **WHEN** an operator needs to validate live PVE readiness before plan/apply-like workflows
- **THEN** the operator SHALL use the explicit PVE preflight command
- **AND** the command SHALL be repository-owned and documented alongside other explicit PVE operations

#### Scenario: Cloud CI runs default validation
- **WHEN** GitHub Actions or another cloud CI runner runs default validation
- **THEN** it SHALL NOT run PVE online preflight
- **AND** it SHALL NOT define PVE API, SSH, 1Password, or apply-capable credentials for that preflight

#### Scenario: Online operation boundaries are documented
- **WHEN** validation documentation lists available checks
- **THEN** it SHALL distinguish offline-safe checks from the explicit PVE online preflight
- **AND** it SHALL state that PVE online preflight is read-only but still requires runtime PVE context

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
