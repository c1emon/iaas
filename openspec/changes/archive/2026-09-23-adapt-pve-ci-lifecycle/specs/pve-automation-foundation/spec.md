## MODIFIED Requirements

### Requirement: Debian 13 PVE template build foundation
The system SHALL provide a fixed-input Debian 13 cloud-init template build process through the supported node executor, separately from VM management, without requiring an existing usable template to be rebuilt.

#### Scenario: Build a reusable Debian 13 template
- **WHEN** an operator invokes the authorized template lifecycle with required PVE connection and storage inputs
- **THEN** the build SHALL produce a Debian 13 template and report actual configuration verification for cloud-init and qemu-guest-agent support
- **AND** the template SHALL use a pinned caller-selected Debian genericcloud image URL and checksum
- **AND** it SHALL use the configured apt mirrors, timezone, locale and build bridge from the fixed recipe
- **AND** machine-specific identity, SSH host keys, cloud-init state and temporary image artifacts SHALL be cleaned using supported steps whose failures are not silently ignored
- **AND** build success SHALL NOT imply cloned-guest or business acceptance

#### Scenario: Keep VM-specific data out of the template
- **WHEN** the Debian 13 template is built
- **THEN** the template SHALL NOT contain fixed VM hostnames, fixed VM IP addresses, VM-specific SSH host keys or application-specific secrets

#### Scenario: Retain existing templates by default
- **WHEN** a new Debian 13 template is built
- **THEN** existing templates SHALL remain unchanged and the new build SHALL use an unoccupied VMID within the supported protection envelope and caller policy
- **AND** the supported runtime and node executor SHALL reject force replacement
- **AND** explicit cleanup or retirement SHALL remain a separately reviewed action with ownership and dependency checks

#### Scenario: Spike the genericcloud import path first
- **WHEN** the template lifecycle implementation is adapted
- **THEN** the repository SHALL reuse the existing genericcloud customization/import capabilities with the new execution and evidence contract
- **AND** documentation SHALL describe supported prerequisites and limitations without requiring a parallel Packer implementation or a live rebuild for software acceptance
