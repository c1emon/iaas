# vm-ansible-bootstrap Specification

## Purpose
Define the explicit, repository-owned Ansible workflow for bootstrapping
declared PVE guest VMs to a common Debian VM baseline after cloud-init handoff.

## Requirements

### Requirement: Explicit VM bootstrap entrypoint
The system SHALL provide an explicit repository-owned Ansible workflow for bootstrapping declared PVE guest VMs to a common baseline.

#### Scenario: Operator bootstraps declared guests
- **WHEN** an operator runs the VM bootstrap command
- **THEN** the system SHALL run a repository-owned Ansible playbook for declared PVE guest VMs
- **AND** it SHALL use the generated PVE Ansible inventory as the host source of truth
- **AND** it SHALL apply a reusable common VM baseline role

#### Scenario: Operator validates bootstrap syntax
- **WHEN** an operator runs the VM bootstrap syntax-check command
- **THEN** the system SHALL syntax-check the bootstrap playbook with the generated PVE Ansible inventory
- **AND** it SHALL NOT connect to guest hosts or mutate guest state during syntax checking

### Requirement: Generated inventory and ops SSH user are authoritative
The system SHALL bootstrap only guests rendered from repository VM inventory and SHALL use the generated SSH connection metadata.

#### Scenario: Bootstrap selects generated PVE guests
- **WHEN** VM bootstrap runs without an operator-provided narrower limit
- **THEN** it SHALL target the generated `pve_vms` inventory group
- **AND** it SHALL NOT discover guests directly from PVE or from ad-hoc host lists

#### Scenario: Bootstrap connects to guests
- **WHEN** Ansible connects to a declared guest for bootstrap
- **THEN** it SHALL use the generated guest SSH user and host address
- **AND** authentication SHALL rely on the operator's SSH agent or configured Ansible SSH authentication
- **AND** repository code SHALL NOT read, write, or print private key material

#### Scenario: Operator limits bootstrap scope
- **WHEN** an operator provides an Ansible limit or equivalent documented scope selector
- **THEN** the bootstrap workflow SHALL restrict execution to matching generated inventory hosts
- **AND** it SHALL NOT require a separate bootstrap inventory file

### Requirement: Common Debian VM baseline convergence
The system SHALL converge Debian cloud-image guest VMs to a common operational baseline suitable for ordinary VMs and future K3s nodes.

#### Scenario: Baseline packages are installed
- **WHEN** VM bootstrap applies the common baseline role to a reachable guest
- **THEN** it SHALL install configured baseline apt packages using Ansible package-management modules
- **AND** the default package set SHALL include qemu-guest-agent readiness and common operator diagnostics needed for VM operations

#### Scenario: Baseline services are enabled
- **WHEN** VM bootstrap applies the common baseline role to a reachable guest
- **THEN** it SHALL ensure configured baseline services such as qemu-guest-agent and time synchronization are enabled or running as declared
- **AND** it SHALL use idempotent Ansible modules where available

#### Scenario: Host identity is converged
- **WHEN** VM bootstrap applies the common baseline role to a reachable guest
- **THEN** it SHALL converge or validate the guest hostname against the generated inventory identity
- **AND** it SHALL keep VM-specific identity out of the reusable template image

#### Scenario: Reboot need is detected
- **WHEN** bootstrap changes packages or host settings that may require a reboot
- **THEN** it SHALL report whether the guest indicates a reboot is required
- **AND** it SHALL NOT reboot guests automatically in the first version

### Requirement: Bootstrap safety boundaries
The system SHALL keep VM bootstrap scoped to guest operating-system baseline changes and SHALL avoid infrastructure or network mutation.

#### Scenario: Bootstrap runs against guests
- **WHEN** VM bootstrap executes
- **THEN** it SHALL NOT create, start, stop, destroy, migrate, import, or modify PVE VM lifecycle state
- **AND** it SHALL NOT mutate PVE host networking, OPNsense, switches, DNS records, K3s clusters, storage services, or application workloads

#### Scenario: Guest network facts are handled
- **WHEN** VM bootstrap evaluates guest network expectations
- **THEN** it MAY validate or report declared IP, route, gateway, DNS, or interface facts
- **AND** it SHALL NOT rewrite guest network configuration, guest routes, or guest DNS configuration in the first version

#### Scenario: Bootstrap is re-run
- **WHEN** an operator re-runs VM bootstrap against an already bootstrapped guest
- **THEN** the workflow SHALL be idempotent for managed baseline state
- **AND** it SHALL avoid reporting changes when the managed state already matches the declared baseline

### Requirement: Bootstrap reporting and follow-up verification
The system SHALL provide operator-readable bootstrap results and preserve read-only guest verification as a separate follow-up workflow.

#### Scenario: Bootstrap completes
- **WHEN** VM bootstrap finishes
- **THEN** Ansible output SHALL identify changed, unchanged, unreachable, and failed guests using standard Ansible reporting
- **AND** failures SHALL include actionable context without disclosing secrets

#### Scenario: Operator verifies bootstrapped guests
- **WHEN** VM bootstrap has run
- **THEN** operators SHALL be able to run the existing PVE guest verification workflow separately
- **AND** guest verification SHALL remain read-only and SHALL NOT remediate bootstrap drift

#### Scenario: Documentation describes the workflow
- **WHEN** operators read the PVE guest automation documentation
- **THEN** it SHALL describe the cloud-init handoff, VM bootstrap command, syntax-check command, guest verification command, safety boundaries, and intended relationship to future K3s node bootstrap

### Requirement: Declarative Debian package-access policy
The system SHALL allow the common Debian VM baseline to consume an optional,
environment-owned package-access policy without changing generated VM facts. A
policy-capable mutation SHALL require an explicitly selected policy-vars file and
SHALL reuse the existing generated `pve_vms` default and narrower-limit behavior.

#### Scenario: No package-access policy is declared
- **WHEN** VM bootstrap runs without an explicit baseline-egress policy
- **THEN** the role SHALL preserve existing APT sources, proxy settings, trust anchors, shell settings, and Git settings
- **AND** existing baseline package behavior SHALL remain unchanged
- **AND** omission SHALL NOT delete previously managed state

#### Scenario: Package-access policy is declared
- **WHEN** a valid policy declares Debian repositories and APT access behavior
- **THEN** the role SHALL verify and install declared repository keyrings before rendering role-owned deb822 source definitions with explicit `Signed-By` paths
- **AND** it SHALL render declared APT proxy, direct-exception, and protected authentication settings before refreshing package metadata
- **AND** it SHALL use Ansible package-management modules rather than raw package-install shell commands

#### Scenario: VM-local bypasses are composed
- **WHEN** proxy and bypass policy is normalized for a generated inventory host
- **THEN** the system SHALL derive the host's declared VM subnets from `pve_nics`
- **AND** it SHALL combine them with validated explicit non-secret bypass destinations
- **AND** it SHALL reject copied host addresses or subnets in the policy document
- **AND** each APT, shell, or Git renderer SHALL accept only representations supported by that consumer, with APT `DIRECT` entries expressed as validated repository hosts rather than CIDRs

#### Scenario: Exclusive source ownership conflicts with unmanaged state
- **WHEN** exclusive managed-source mode is selected and an unknown enabled APT source remains
- **THEN** bootstrap SHALL fail with the conflicting path before any host mutation
- **AND** it SHALL NOT delete or disable the unknown source automatically

#### Scenario: Managed policy is retired
- **WHEN** policy explicitly selects `absent` with declared managed identities
- **THEN** bootstrap SHALL resolve only their fixed, deterministically named role-owned paths
- **AND** any identity or resolved path outside that fixed ownership boundary SHALL fail before deletion
- **AND** bootstrap SHALL remove only the declared role-owned keyring, CA, APT source, proxy/auth, shell, and Git artifacts
- **AND** it SHALL refresh system trust or APT metadata only when removed managed state requires it
- **AND** it SHALL leave unknown or unmanaged files unchanged

### Requirement: Verified trust and credential protection
The system SHALL protect additional trust material and authenticated package
access throughout validation and bootstrap.

#### Scenario: Repository signing key is declared
- **WHEN** a managed APT source references a repository signing key
- **THEN** policy SHALL declare either a role-managed key artifact with exact SHA-256 or an explicitly allowed package-managed absolute keyring path with expected fingerprint
- **AND** a role-managed source artifact SHALL have its digest verified on the controller before mutation and SHALL then be installed atomically into the fixed role-owned keyring directory
- **AND** a package-managed keyring SHALL already exist on the host, be readable by APT, and match the expected fingerprint before any mutation
- **AND** it SHALL NOT use `apt-key`, an unscoped global trusted keyring, or a downloaded key without verified identity

#### Scenario: A custom CA is declared
- **WHEN** policy references a custom CA required for package or proxy TLS
- **THEN** bootstrap SHALL verify its exact SHA-256 identity and confirm the trust-refresh tool exists before installing it into the system trust store
- **AND** it SHALL refresh trust only when managed CA content changes
- **AND** it SHALL NOT disable TLS verification as a substitute

#### Scenario: Authenticated package access is required
- **WHEN** an APT proxy or repository requires credentials
- **THEN** committed policy SHALL contain only runtime secret references
- **AND** rendered credential-bearing files SHALL be root-owned with restrictive permissions
- **AND** resolved values SHALL NOT enter CLI arguments, generated or cached variables, Ansible facts/fact cache, diffs, or ordinary controller temporary files
- **AND** validation and Ansible output SHALL redact the resolved values and protected temporary material SHALL be removed after the action

#### Scenario: Required runtime secret is absent
- **WHEN** a declared authenticated source or proxy cannot resolve its runtime secret
- **THEN** bootstrap SHALL fail before changing trust, source, proxy, or package state

### Requirement: Optional shell and Git proxy policy
The system SHALL keep global shell and Git proxy configuration independently
optional and disabled by default.

#### Scenario: Non-secret global tool proxy is enabled
- **WHEN** policy explicitly enables shell or Git proxy configuration with a non-secret endpoint
- **THEN** bootstrap SHALL manage only the corresponding declared global setting
- **AND** Git proxy configuration SHALL require Git to be already installed
- **AND** bootstrap SHALL NOT install Git solely to configure its proxy

#### Scenario: Authenticated global tool proxy is requested
- **WHEN** global shell or Git policy contains credentials or a runtime secret reference
- **THEN** validation SHALL fail before host mutation
- **AND** documentation SHALL direct authenticated use to protected per-command runtime injection

### Requirement: Ordered and idempotent baseline convergence
The system SHALL validate and apply baseline-egress policy before installing
baseline packages while preserving existing guest-only safety boundaries.

#### Scenario: Valid policy is applied
- **WHEN** VM bootstrap applies a declared baseline-egress policy
- **THEN** it SHALL validate the complete policy, secrets, required host tools, signing keyrings, and unmanaged-source conflicts before the first mutation
- **AND** it SHALL apply repository keyrings, trust, APT sources and proxy, package metadata, packages, and optional tool proxy settings in that order

#### Scenario: Bootstrap is repeated
- **WHEN** the same validated policy is applied to already converged managed files
- **THEN** bootstrap SHALL report no unnecessary changes
- **AND** it SHALL NOT refresh trust or APT metadata solely because the role ran again

#### Scenario: Safety boundary is preserved
- **WHEN** baseline-egress policy is applied
- **THEN** it SHALL modify only declared guest operating-system files and package state
- **AND** it SHALL NOT modify guest interfaces, routes, DNS, firewall, PVE lifecycle, K3s/containerd registry policy, or workload state

### Requirement: Software-only acceptance boundary
The system SHALL allow this capability increment to be accepted without applying
package-access policy to a real guest.

#### Scenario: Capability implementation is accepted
- **WHEN** the change is validated with synthetic inventory and policy fixtures
- **THEN** acceptance SHALL use focused validation, rendering, Ansible syntax/lint, idempotence, redaction, and safety-boundary tests
- **AND** it SHALL NOT require template rebuild, PVE access, guest bootstrap, package-repository access, proxy access, or external mutation
