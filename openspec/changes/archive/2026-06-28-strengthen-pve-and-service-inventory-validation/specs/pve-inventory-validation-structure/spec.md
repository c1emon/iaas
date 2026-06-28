## MODIFIED Requirements

### Requirement: PVE inventory validation errors include field context
The system SHALL report expected PVE inventory validation failures with enough source-field context for operators to fix YAML input without reading Python tracebacks.

#### Scenario: VM static IP is malformed
- **WHEN** a VM declaration contains a `static_ip` value that cannot be parsed as an IP interface
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** it SHALL report the failure as a repository validation error
- **AND** the error message SHALL identify the affected VM and `static_ip` field
- **AND** the failure SHALL NOT require live PVE infrastructure access

#### Scenario: VM static IP does not match the selected network
- **WHEN** a VM declaration contains a `static_ip` whose address family, prefix length, or address range does not match the VM's selected declared network
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** the error message SHALL identify the affected VM and `static_ip` field or selected network context
- **AND** the failure SHALL NOT require live PVE infrastructure access

#### Scenario: VM static IP is not a usable unique host address
- **WHEN** a VM declaration contains a `static_ip` that is the selected network address, the selected network broadcast address, or duplicates another declared VM host address
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** the error message SHALL identify the affected VM and `static_ip` field or duplicate address context
- **AND** the failure SHALL NOT require live PVE infrastructure access

### Requirement: PVE VM inventory identifiers are downstream-safe
The system SHALL reject PVE VM inventory identifiers that are unsafe for their downstream generated uses before rendering OpenTofu variables, Ansible inventory, or generated documentation.

#### Scenario: VM name is safe for hostname-oriented use
- **WHEN** a VM declaration is validated offline
- **THEN** its `name` SHALL be a non-empty lower-case DNS-label-safe value using only letters, digits, and hyphens
- **AND** the name SHALL start and end with a letter or digit
- **AND** the name SHALL fit within a single hostname label length
- **AND** invalid values SHALL fail with context identifying the affected VM `name` field

#### Scenario: Ansible group names are safe for generated inventory
- **WHEN** a VM declaration includes `ansible_groups`
- **THEN** each group SHALL be a non-empty string using an Ansible-safe lower-case inventory group identifier format
- **AND** duplicate group values within the same VM declaration SHALL be rejected explicitly
- **AND** invalid values SHALL fail before generated Ansible inventory is accepted
- **AND** the failure SHALL identify the affected VM and `ansible_groups` field context

#### Scenario: PVE tag values are safe for provider/PVE use
- **WHEN** a VM declaration includes `tags`
- **THEN** each tag SHALL be a non-empty string using the PVE/OpenTofu-provider-safe tag token set
- **AND** tag values SHALL NOT contain whitespace or delimiter characters that would corrupt comma-joined provider inputs
- **AND** duplicate tag values within the same VM declaration SHALL be rejected explicitly
- **AND** invalid values SHALL fail before generated OpenTofu variables, PVE VM documentation, or preflight expectations are accepted
- **AND** the failure SHALL identify the affected VM and `tags` field context

#### Scenario: Current inventory remains valid under hardened rules
- **WHEN** the repository's current `inventory/vms.yml` is validated offline
- **THEN** VM names, Ansible groups, PVE tags, and static IPs SHALL pass the hardened rules
- **AND** generated OpenTofu variables, Ansible inventory, PVE VM documentation, and template build environment output SHALL preserve the same schemas and meanings for unchanged valid input
