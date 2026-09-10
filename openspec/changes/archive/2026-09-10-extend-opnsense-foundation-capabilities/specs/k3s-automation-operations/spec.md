## ADDED Requirements

### Requirement: Operation-aware lifecycle admission
Shared K3s read-only probes SHALL be evaluated against the requested install, declared-state convergence or upgrade operation, retaining scope and ownership protections.

#### Scenario: Lifecycle admission mode is selected
- **WHEN** standalone preflight is invoked
- **THEN** it SHALL require `K3S_PREFLIGHT_MODE=install|converge|upgrade`, or the equivalent `k3s_preflight_mode` for direct Ansible use
- **AND** missing or unknown modes SHALL fail before credential or host access
- **AND** deploy SHALL select converge and upgrade SHALL select upgrade without accepting an override that bypasses their operation's policy

#### Scenario: Installation state does not support the requested operation
- **WHEN** install encounters an existing installation or partial artifact, or upgrade encounters a fresh or incomplete installation
- **THEN** admission SHALL fail before mutation
- **AND** converge MAY admit a fresh host but SHALL reject a prior installed version and direct the caller to upgrade
- **AND** binary presence alone SHALL NOT prove ownership of configuration or a datastore

#### Scenario: A declared installed cluster is upgraded or converged
- **WHEN** installed binaries, configuration and listeners belong to the declared supported cluster
- **THEN** expected K3s installation and port use SHALL NOT be classified as fresh-install conflicts
- **AND** incompatible or foreign state SHALL still fail before mutation

#### Scenario: Deployment resumes after artifact acquisition
- **WHEN** an earlier invocation acquired the exact declared artifact but stopped before configuration or service start
- **THEN** deployment SHALL admit that supported partial state after validating its identity
- **AND** it SHALL NOT use deployment re-entry to bypass upgrade transition rules

### Requirement: Truthful host and upgrade observations
K3s admission and success reporting SHALL use actual parsed host and cluster observations, not inferred copies of desired values.

#### Scenario: Host prerequisite differs from intent
- **WHEN** capability bits lack a required capability or the exact derived IP is absent from its required runtime interface
- **THEN** preflight SHALL report the failed condition and block mutation
- **AND** missing, malformed or unreachable required observations SHALL NOT pass
- **AND** substring IP matches and mere presence of a CapEff field SHALL NOT establish correctness

#### Scenario: Upgrade observation has become stale
- **WHEN** actual node versions differ from caller-supplied observations
- **THEN** the upgrade SHALL fail before its first mutation and require refreshed observations
- **AND** a claimed target version SHALL NOT cause an unverified skip

#### Scenario: An upgraded node is verified
- **WHEN** each node completes its upgrade stage
- **THEN** the workflow SHALL verify its exact identity, target version and role-appropriate service and cluster health before advancing
- **AND** an old Node name alone SHALL NOT establish registration, version or readiness
- **AND** completion SHALL reuse staged whole-scope verification with only the existing explicit external-CNI bootstrap exception

### Requirement: Stage upgrade artifacts before service interruption
Upgrade SHALL acquire and verify the target executable before stopping the active service, preserving serial server-before-agent ordering and pre-upgrade snapshot requirements.

#### Scenario: Download or checksum verification fails
- **WHEN** acquisition of the staged target artifact fails
- **THEN** the active executable and running service SHALL remain unchanged
- **AND** the workflow SHALL identify the failed node and phase

#### Scenario: A verified target is activated
- **WHEN** the staged artifact matches the checksum and exact target binary version
- **THEN** the workflow MAY stop the selected service, replace its executable and restart it
- **AND** a failed stop SHALL prevent executable replacement
- **AND** readiness verification SHALL have a finite retry budget and retain systemd startup semantics

#### Scenario: Activation fails
- **WHEN** executable activation or subsequent health verification fails
- **THEN** later nodes SHALL remain untouched and the workflow SHALL fail with explicit phase and recovery guidance
- **AND** it SHALL NOT implicitly downgrade an activated version, restore etcd or replace the datastore

### Requirement: Application-neutral artifact locations
The K3s artifact contract SHALL accept caller-selected safe HTTPS locations independently of provider-specific URL path conventions while retaining exact version and checksum requirements.

#### Scenario: Artifact comes from a private or differently structured repository
- **WHEN** the caller supplies a safe explicit HTTPS URL, exact K3s version and SHA-256
- **THEN** validation SHALL NOT require a particular mirror provider or version path spelling
- **AND** version and integrity SHALL be verified against the staged executable before activation
- **AND** existing credential, proxy and unpinned-installer prohibitions SHALL remain in force
