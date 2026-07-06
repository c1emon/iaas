## ADDED Requirements

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
