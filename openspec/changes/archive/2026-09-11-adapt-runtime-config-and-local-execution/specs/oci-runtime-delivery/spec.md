## ADDED Requirements

### Requirement: Launcher delivery and compatibility metadata
Runtime delivery SHALL include a separately installable versioned launcher and a documented compatibility contract without adding host toolchains to ordinary runtime prerequisites.

#### Scenario: Install or upgrade a launcher
- **WHEN** a caller installs or explicitly upgrades the launcher
- **THEN** project-owned instructions SHALL provide supported host artifacts, standard checksums, prerequisites and compatibility guidance
- **AND** caller image/configuration selections SHALL NOT be silently changed
- **AND** runtime execution SHALL NOT auto-update the launcher

#### Scenario: Assemble the adapted image
- **WHEN** the adapted runtime image is built
- **THEN** it SHALL contain the new runtime parser/dispatcher and necessary compatibility metadata while preserving existing runtime-only content and dependency layering rules
- **AND** real caller configuration, backend values, plans and credentials SHALL remain excluded

### Requirement: Explicit platform capability
The runtime SHALL support Linux amd64 and documented Apple Silicon local use with explicit container-platform selection, and SHALL publish the evaluated scope of native Linux arm64 support.

#### Scenario: Build a native ARM64 image
- **WHEN** a caller selects `RUNTIME_PLATFORM=linux/arm64` for the image build
- **THEN** the build SHALL use pinned ARM64 tools and their checksums, and CI SHALL build and check AMD64 and ARM64 serially
- **AND** launcher admission SHALL match the requested platform against the running image architecture
- **AND** saved plans SHALL bind that architecture and reject cross-architecture reuse before infrastructure writes
- **AND** software build validation SHALL NOT imply real-facility qualification

#### Scenario: Publish one version for both architectures
- **WHEN** a published Release triggers image distribution
- **THEN** both native architectures SHALL be built and tested serially before the publication job is admitted
- **AND** image CI jobs SHALL use the same pinned Docker CLI/Engine baseline supporting platform-specific image inspection, with consistent image storage and daemon selection across temporary authentication directories
- **AND** publication SHALL load those tested artifacts without rebuilding, check their source labels and platform identities, and publish a version manifest containing exactly Linux AMD64 and ARM64
- **AND** existing version and architecture tags SHALL NOT be overwritten; only the same tested artifacts may resume a partial or completed publication
- **AND** anonymous consumption SHALL pull the shared manifest digest and execute the expected platform on both architectures
- **AND** historical single-platform tags SHALL remain unchanged

#### Scenario: Inject publication credentials in CI
- **WHEN** CI publishes image or launcher assets
- **THEN** publication credentials SHALL be explicitly supplied by the CI platform
- **AND** publication SHALL run noninteractively without obtaining credentials from local 1Password or developer shell startup files

#### Scenario: Run on Apple Silicon
- **WHEN** a caller selects a supported Apple Silicon launcher and Linux amd64 container mode
- **THEN** documentation and startup checks SHALL identify the required container-engine emulation capability and operation limitations
- **AND** incompatible engine/platform combinations SHALL fail rather than silently selecting another platform

#### Scenario: Evaluate native arm64
- **WHEN** native Linux arm64 support is assessed
- **THEN** the result SHALL identify supported and unsupported operations from actual tool/provider compatibility evidence
- **AND** unsupported combinations SHALL be rejected or require an explicitly selected amd64 alternative
- **AND** unexecuted platforms SHALL NOT be labeled validated

### Requirement: Bounded runtime adaptation acceptance
Acceptance SHALL use grouped representative workflows and distinguish software validation from actual platform/daemon/S3 service validation.

#### Scenario: Run software checks
- **WHEN** the adaptation is validated with synthetic inputs
- **THEN** grouped checks SHALL cover offline operation, path/reference failures, component scope, version compatibility, permissions, saved plans and recovery retention
- **AND** tests SHALL exercise phase failures without real infrastructure mutations or live credentials

#### Scenario: Validate actual execution modes
- **WHEN** local Docker, Apple Silicon, Forgejo DinD or a selected S3-compatible service is reported as accepted
- **THEN** that execution mode SHALL have actual evidence from a separately identified and authorized bounded environment
- **AND** mocks, another platform or simple S3 upload/download SHALL NOT substitute for the claimed mode's path/permission or native-lock behavior
- **AND** absent evidence SHALL remain explicitly pending without triggering shared-environment access automatically

### Requirement: Canonical adaptation guidance
The IaaS repository SHALL own installation, operation, migration and troubleshooting guidance; callers SHALL own environment values, backend selection, credentials and authorization.

#### Scenario: Adopt the new interface
- **WHEN** a caller follows migration guidance
- **THEN** it SHALL describe component configuration, runtime selection, local/DinD execution, S3 state and saved-plan/recovery outputs
- **AND** it SHALL preserve existing explicit entrypoints or give clear versioned errors without rewriting sources or migrating state
- **AND** it SHALL distinguish serial workflow assumptions and deferred concurrency alternatives from implemented guarantees
