## MODIFIED Requirements

### Requirement: Guest user and automation access model
The system SHALL create separate human and automation users in new VMs, avoid direct root SSH automation by default, and configure the automation user for repository-owned non-interactive automation.

#### Scenario: Create human and automation users
- **WHEN** cloud-init initializes a new VM
- **THEN** it SHALL create or configure `clemon` as the human administration user
- **AND** it SHALL create or configure `ops` as the automation user
- **AND** `clemon` SHALL retain password-protected sudo capability
- **AND** `ops` SHALL have explicit non-interactive sudo capability suitable for repository-owned Ansible become and guest verification

#### Scenario: Render Section 4A guest users at runtime
- **WHEN** the Section 4A runtime helper renders a VM user-data snippet
- **THEN** it SHALL create both `clemon` and `ops`
- **AND** it SHALL set password-protected sudo for `clemon`
- **AND** it SHALL set non-interactive sudo for `ops`
- **AND** it SHALL disable direct root login, disable SSH password authentication, and disable package update/upgrade on first boot
- **AND** it SHALL source passwords and SSH public keys from runtime 1Password-provided environment variables

#### Scenario: Connect Ansible through the automation user
- **WHEN** Ansible inventory is generated for managed VMs
- **THEN** the inventory SHALL use `ops` as the default Ansible connection user
- **AND** it SHALL configure sudo become to root for privileged operations
- **AND** the rendered guest configuration SHALL allow this repository-owned automation path to run non-interactively
- **AND** the inventory SHALL NOT contain sudo passwords, login passwords, private keys, token secrets, or password hashes
