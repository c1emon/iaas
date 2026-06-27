## MODIFIED Requirements

### Requirement: Guest checks are read-only
The system SHALL verify guest state using read-only Ansible checks and SHALL NOT remediate drift.

#### Scenario: Guest is reachable
- **WHEN** guest verification can connect to a declared guest
- **THEN** it SHALL check the guest hostname, declared static IP, qemu-guest-agent state, `ops` non-interactive sudo capability, root SSH disablement, and expected inventory metadata where available
- **AND** `ops` non-interactive sudo capability SHALL be evaluated as a hard guest readiness check for reachable guests
- **AND** it SHALL report each check outcome clearly

#### Scenario: Guest drift is found
- **WHEN** a reachable guest does not match expected identity, IP, agent, sudo, SSH, or metadata expectations
- **THEN** guest verification SHALL report the mismatch
- **AND** it SHALL NOT change hostname, network configuration, packages, users, sudoers, SSHD configuration, DNS, firewall, switch, or PVE state
