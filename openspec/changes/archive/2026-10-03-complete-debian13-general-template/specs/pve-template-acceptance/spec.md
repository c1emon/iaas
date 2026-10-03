## ADDED Requirements

### Requirement: Representative general template clone acceptance
The requested real acceptance SHALL use one temporary full clone in the existing dedicated pool, independently configure NIC/network/DNS and instance identity before first boot, expand its system disk to 128 GiB, verify actual guest partition/filesystem growth and network, cloud-init and agent, preserve template 9000 and clean exact execution-owned temporary resources.

#### Scenario: Complete the real mainline
- **WHEN** template 9000 was built and published with 2 cores, 1 GiB memory, 8 GiB disk and no NIC
- **THEN** a dedicated-pool temporary clone SHALL use 8 cores, 8 GiB memory and 128 GiB disk with br_dev, 10.10.0.100/24, gateway 10.10.0.254 and DNS 10.5.0.15 before boot
- **AND** actual guest checks SHALL confirm root partition/filesystem expansion, independent identity, cloud-init completion and responsive Guest Agent
- **AND** source configuration SHALL remain unchanged and execution-owned VM/volumes/snippets SHALL be removed

#### Scenario: Distinguish acceptance scopes
- **WHEN** only offline checks, fixtures or software CI pass, or real execution is blocked
- **THEN** the delivery SHALL explicitly preserve the missing real acceptance conclusion
- **AND** even successful real template acceptance SHALL NOT imply infra-ops daily apply admission or deployment/business acceptance
