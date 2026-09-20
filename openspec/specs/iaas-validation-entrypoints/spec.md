# iaas-validation-entrypoints Specification

## Purpose
Define the repository-owned offline validation command surface used by local
operators and CI, while keeping online infrastructure checks, planning, and
mutation-capable operations explicit.

## Requirements

### Requirement: Root offline validation command surface
The system SHALL expose root-level commands that provide routine offline validation for the explicitly selected environment to local operators and CI.

#### Scenario: Generate committed outputs from source inventory
- **WHEN** an operator runs the root generation command
- **THEN** the system SHALL regenerate non-sensitive outputs beneath the explicitly selected generated-output directory from the selected environment's authored source files
- **AND** it SHALL include generated service metadata documentation from the selected environment's `inventory/services.yml`
- **AND** it SHALL use repository-owned generator behavior and paths supplied by the root command rather than ad-hoc shell snippets
- **AND** it SHALL NOT require PVE API connectivity or runtime secrets

#### Scenario: Detect stale generated outputs
- **WHEN** selected environment source data changes without updating its committed generated outputs
- **THEN** the root generated-output check SHALL fail
- **AND** it SHALL report stale PVE, service, or foundation artifacts as applicable
- **AND** it SHALL NOT modify files while running in check mode

#### Scenario: Run the aggregate offline gate
- **WHEN** an operator or CI runs the root aggregate check command
- **THEN** the system SHALL run only infrastructure-offline validation targets for the selected environment
- **AND** it SHALL include generated-output freshness, Python tests, YAML lint, OpenTofu formatting/validation, Python type checking, Ansible lint/syntax as applicable, and OPNsense desired-state validation
- **AND** it SHALL fail when any required validation fails
- **AND** it SHALL NOT generate or render files, access online infrastructure, read runtime secrets, plan, or mutate infrastructure

#### Scenario: Install locked toolchains before validation
- **WHEN** cloud CI validates a pull request or main-branch update
- **THEN** it SHALL install the committed Python and infrastructure validation toolchains without making OpenSpec a project runtime dependency
- **AND** it SHALL invoke the same repository-owned aggregate offline command used by operators
- **AND** it SHALL report validation failures without executing online, planning, or mutation workflows

#### Scenario: Caller omits environment selection
- **WHEN** a root operation needs authored environment data but receives no complete explicit environment/file inputs
- **THEN** it SHALL fail before generation, online access or mutation with a generic input requirement
- **AND** it SHALL NOT fall back to Astra paths or accept a removed `ASTRA` selector
- **AND** environment-independent commands SHALL remain usable without unrelated inputs

### Requirement: Validation CLI failures are operator-readable
The system SHALL convert expected repository validation failures at CLI boundaries into stable operator-readable errors.

#### Scenario: PVE inventory CLI receives invalid operator-authored input
- **WHEN** a PVE inventory CLI command fails because source-of-truth input is invalid, including hardened identifier or static IP validation failures
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL identify enough source-field context for operator correction
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material

#### Scenario: Services inventory CLI receives invalid operator-authored input
- **WHEN** a services inventory CLI command fails because source-of-truth input is invalid
- **THEN** the command SHALL exit with status `1`
- **AND** it SHALL print a concise validation failure message to stderr
- **AND** it SHALL NOT print a Python traceback for that expected validation failure
- **AND** it SHALL NOT disclose runtime secrets or credential material

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
The system SHALL keep PR/main CI limited to validation and image build/smoke checks without internal infrastructure privileges or image publication. A separate Release publication workflow SHALL follow the `oci-runtime-delivery` contract.

#### Scenario: Validate a pull request in cloud CI
- **WHEN** a pull request triggers the CI workflow
- **THEN** GitHub Actions SHALL install the required locked validation toolchain and explicitly select validation inputs
- **AND** it SHALL call repository-owned offline validation commands
- **AND** it SHALL report success or failure to the Git provider
- **AND** it SHALL NOT require internal network routes or infrastructure secrets

#### Scenario: Validate main branch updates in cloud CI
- **WHEN** changes are pushed to the main branch
- **THEN** CI SHALL run the same offline validation gate used for pull requests with explicit environment/output selection
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
- **WHEN** operators need to validate live PVE readiness or health
- **THEN** they SHALL use explicit online targets or workflows separate from the aggregate offline check
- **AND** the default offline check SHALL NOT depend on PVE online preflight or PVE cluster health targets

#### Scenario: Preserve explicit planning and mutation operations
- **WHEN** operators need to run OpenTofu plan, OpenTofu apply, OpenTofu destroy, Packer template builds, Ansible mutation, PVE maintenance, VM migration, package updates, node reboot workflows, or Ceph mutation
- **THEN** those operations SHALL remain explicit commands or manual runbook steps
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

### Requirement: Explicit PVE guest verification remains outside offline validation
The system SHALL expose PVE guest verification as an explicit online operation separate from default offline validation.

#### Scenario: Operator requests guest verification
- **WHEN** an operator needs to validate guest-side readiness for declared PVE VMs
- **THEN** the operator SHALL use the explicit PVE guest verification command
- **AND** the command SHALL be repository-owned and documented alongside other explicit PVE operations

#### Scenario: Cloud CI runs default validation
- **WHEN** GitHub Actions or another cloud CI runner runs default validation
- **THEN** it SHALL NOT run PVE guest verification
- **AND** it SHALL NOT define guest SSH, PVE API, 1Password, or apply-capable credentials for that verification

#### Scenario: Validation documentation lists guest verification
- **WHEN** validation documentation lists available checks
- **THEN** it SHALL distinguish offline-safe checks from explicit PVE guest verification
- **AND** it SHALL state that PVE guest verification is read-only but still requires runtime guest SSH context

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
- **AND** it SHALL NOT run PVE preflight, PVE cluster health checks, PVE rolling maintenance, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, or infrastructure mutation

#### Scenario: Runtime state artifacts are accidentally tracked
- **WHEN** local OpenTofu state, provider directories, virtual environments, caches, Ansible collections, or platform metadata files are accidentally added to source control
- **THEN** repository hygiene checks or reviewable repository rules SHALL reject or clearly surface the tracked runtime artifact as a failure
- **AND** the default offline check SHALL NOT delete ignored local runtime artifacts automatically

#### Scenario: Validation documentation lists available local checks
- **WHEN** an operator reads the local validation documentation
- **THEN** it SHALL distinguish default offline checks from optional explicit hygiene checks
- **AND** it SHALL identify which commands are safe anywhere and which commands require explicit online/runtime context

### Requirement: Executable conversion invariants and dependency boundaries
The offline gate SHALL check bounded normalization properties and the established dependency direction of common primitives, OPNsense conversion and pure declaration validation. These checks SHALL require no infrastructure access or runtime credentials and SHALL not replace existing deterministic regression cases.

#### Scenario: Conversion property fails
- **WHEN** normalization changes an already canonical record, mutates its input, mishandles equivalent aliases or exposes synthetic sensitive input
- **THEN** the relevant property check fails with a reproducible counterexample
- **AND** generated cases remain bounded to the declared input domain

#### Scenario: Pure layer imports execution behavior
- **WHEN** common imports a domain or online adapter, conversion imports a workflow executor or transport, or pure declaration validation imports an online workflow adapter
- **THEN** the repository-owned dependency check fails in both local and CI validation
- **AND** normal domain-to-common imports remain permitted

### Requirement: Explicit fast and domain validation profiles
The repository SHALL expose environment-independent fast checks and named domain test profiles alongside the full offline test and check commands. Fast checks SHALL use an explicit bounded set of pure offline tests, SHALL report subset coverage and SHALL fail for an empty selected set. They SHALL not require inventory selection, runtime credentials, image builds or external infrastructure tools.

#### Scenario: Developer runs fast validation
- **WHEN** a developer requests the fast profile without environment inventory, Docker, Ansible execution or device credentials
- **THEN** the selected pure Python tests and configured static checks can execute
- **AND** the report does not claim full repository or appliance acceptance

#### Scenario: Domain profile is selected
- **WHEN** a developer selects the OPNsense, PVE or K3s test profile
- **THEN** the repository-owned command runs the documented offline domain set and propagates failure
- **AND** it does not implicitly invoke a device operation

### Requirement: Fast profiles preserve complete validation
Adding profiles SHALL preserve collection of all existing tests by the full test command and preserve the aggregate offline gate used by CI. External-tool integration and image smoke checks SHALL remain explicit and SHALL not be mistaken for pure fast tests.

#### Scenario: Test has no profile marker
- **WHEN** an existing or new test has no fast or integration marker
- **THEN** the full test command still collects it
- **AND** the fast profile does not silently treat it as a verified fast test

#### Scenario: Full CI validation runs
- **WHEN** PR or main CI invokes the aggregate offline gate
- **THEN** existing required validation remains present regardless of fast-profile results

### Requirement: Validation performance claims are measured
Performance reports SHALL identify the executed test set, runtime environment and measured timings. Parallel execution SHALL be opt-in for tested isolated offline groups and SHALL not enable concurrent device operations.

#### Scenario: Faster feedback is reported
- **WHEN** an implementation reports a speed improvement
- **THEN** it provides comparable measurements and discloses omitted checks
- **AND** absence of a measured parallelism benefit does not cause parallel execution to be enabled by default

### Requirement: Scoped non-mutating Python quality checks
Repository validation SHALL include Python lint and stricter type checks for an explicitly configured set of new boundary modules. The scope SHALL be consistent between local and CI execution and SHALL exclude vendored and generated code. Quality checks SHALL not modify files, contact infrastructure or require runtime credentials.

#### Scenario: Selected module violates a quality rule
- **WHEN** a configured source file contains an enabled lint violation or strict type error
- **THEN** the repository-owned quality gate fails in both fast and full validation
- **AND** no automatic fix or reformat is applied

#### Scenario: Unrelated legacy module is checked
- **WHEN** a legacy file outside the stricter scope is part of existing project validation
- **THEN** its previous type-checking mode remains in force
- **AND** the new gate does not trigger an unrelated repository-wide formatting migration

#### Scenario: CI and local checks run the same commit
- **WHEN** local and CI invoke the quality gate with the same locked tools and source tree
- **THEN** both use the same configured rule and path sets regardless of Git comparison base
