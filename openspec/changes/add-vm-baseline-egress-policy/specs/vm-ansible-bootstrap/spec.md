## ADDED Requirements

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
