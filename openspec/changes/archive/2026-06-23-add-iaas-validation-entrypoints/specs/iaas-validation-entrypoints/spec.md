## ADDED Requirements

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
