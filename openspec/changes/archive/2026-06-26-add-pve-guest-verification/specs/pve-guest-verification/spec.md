## ADDED Requirements

### Requirement: Explicit PVE guest verification entrypoint
The system SHALL expose an explicit repository-owned PVE guest verification command for local operators.

#### Scenario: Operator verifies declared PVE guests
- **WHEN** an operator runs the PVE guest verification command
- **THEN** the system SHALL verify guest-side readiness for repo-managed VMs declared in the repository source of truth
- **AND** it SHALL use repository-owned command targets rather than ad-hoc shell snippets
- **AND** it SHALL NOT create, start, stop, destroy, or modify VMs or guests

#### Scenario: No repo-managed guests are declared
- **WHEN** the generated PVE guest inventory contains no repo-managed guest VMs
- **THEN** guest verification SHALL report that there are no guests to verify
- **AND** it SHALL exit successfully with a skipped result

### Requirement: Generated inventory and ops SSH user are authoritative
The system SHALL verify only guests rendered from the repository-generated PVE Ansible inventory and SHALL use the `ops` guest SSH user for first-version checks.

#### Scenario: Guest verification selects hosts
- **WHEN** guest verification runs
- **THEN** it SHALL target the generated PVE inventory group for declared VMs
- **AND** it SHALL NOT attempt to discover or verify every VM visible in PVE

#### Scenario: Guest SSH credentials are needed
- **WHEN** Ansible connects to declared guests
- **THEN** it SHALL use the `ops` SSH user from generated inventory
- **AND** authentication SHALL rely on the operator's SSH agent or 1Password SSH Agent
- **AND** repository code SHALL NOT read, write, or print private key material

### Requirement: Guest checks are read-only
The system SHALL verify guest state using read-only Ansible checks and SHALL NOT remediate drift.

#### Scenario: Guest is reachable
- **WHEN** guest verification can connect to a declared guest
- **THEN** it SHALL check the guest hostname, declared static IP, qemu-guest-agent state, `ops` non-interactive sudo capability, root SSH disablement, and expected inventory metadata where available
- **AND** it SHALL report each check outcome clearly

#### Scenario: Guest drift is found
- **WHEN** a reachable guest does not match expected identity, IP, agent, sudo, SSH, or metadata expectations
- **THEN** guest verification SHALL report the mismatch
- **AND** it SHALL NOT change hostname, network configuration, packages, users, sudoers, SSHD configuration, DNS, firewall, switch, or PVE state

### Requirement: Offline and DNS findings are non-blocking in the first version
The system SHALL treat intentionally variable guest availability and DNS readiness as warning-class findings in the first version.

#### Scenario: Declared guest is offline or unreachable
- **WHEN** a declared repo-managed guest cannot be reached over SSH
- **THEN** guest verification SHALL report the guest as unreachable with warning severity
- **AND** it SHALL continue evaluating other guests when possible
- **AND** it SHALL exit successfully if no hard failures are present

#### Scenario: DNS check fails
- **WHEN** a declared guest's DNS-related checks do not match expectations
- **THEN** guest verification SHALL report the DNS issue with warning severity
- **AND** it SHALL exit successfully if no hard failures are present

### Requirement: Guest verification reporting and exit semantics
The system SHALL provide operator-readable guest verification results that distinguish pass, warn, fail, and skipped checks.

#### Scenario: Only warnings or skipped checks are found
- **WHEN** guest verification completes with no hard failures but with warnings or skipped checks
- **THEN** it SHALL exit successfully
- **AND** it SHALL report warnings and skipped checks clearly for operator review

#### Scenario: Hard verification failure is found
- **WHEN** guest verification finds a hard failure in a reachable guest or cannot run its verification workflow correctly
- **THEN** it SHALL exit with a non-zero status
- **AND** it SHALL report actionable failure context without disclosing secrets

#### Scenario: All guest checks pass
- **WHEN** all applicable guest verification checks pass
- **THEN** it SHALL report successful guest verification for the declared PVE guests
