## MODIFIED Requirements

### Requirement: YAML source-of-truth for PVE VM automation
The system SHALL use operator-authored YAML inventory as the source of truth for PVE cluster defaults, networks, templates, PCI resource mappings, and VM declarations.

#### Scenario: Generate OpenTofu and Ansible inputs from one VM declaration
- **WHEN** an operator declares a VM with node, template, network or NICs, static IP addressing, sizing, lifecycle, and Ansible group data in YAML
- **THEN** the system SHALL generate OpenTofu input for VM provisioning from that declaration
- **AND** it SHALL generate Ansible inventory entries from the same declaration
- **AND** it SHALL generate human-readable VM documentation from the same declaration
- **AND** it SHALL avoid requiring duplicate manual VM definitions in OpenTofu and Ansible

#### Scenario: Reject legacy single-NIC VM fields
- **WHEN** an operator declares a VM using the removed top-level `network`, `static_ip`, `gateway`, or `dns` fields
- **THEN** validation SHALL reject the declaration
- **AND** the error message SHALL point to the deprecated top-level fields

#### Scenario: Declare a multi-NIC VM
- **WHEN** an operator declares a VM with a `nics` list
- **THEN** each NIC SHALL declare a stable name, semantic role, logical network, static CIDR address, and deterministic MAC address
- **AND** each NIC MAY declare explicit `default_route` and `ansible_connection` metadata, plus optional gateway and DNS settings subject to validation
- **AND** the declaration SHALL NOT require any particular role in the generic base model

#### Scenario: Keep generated files reviewable and non-sensitive
- **WHEN** the generator emits OpenTofu, Ansible, documentation, or cloud-init metadata outputs
- **THEN** it SHALL write `infra/tofu/pve/generated.auto.tfvars.json`, `ansible/inventories/generated/pve.yml`, and generated VM documentation as committed non-sensitive files
- **AND** those generated files SHALL NOT contain passwords, password hashes, private keys, token secrets, or other secrets
- **AND** repository ignore rules SHALL explicitly allow any generated files that are intended to be committed
- **AND** validation SHALL detect when committed generated files are stale relative to source YAML

#### Scenario: Reject inconsistent source data before provisioning
- **WHEN** YAML inventory contains duplicate VM IDs, duplicate hostnames, duplicate IP addresses, duplicate MAC addresses, unknown nodes, unknown templates, unknown networks, invalid NIC roles, multiple default-route NICs, or multiple Ansible-connection NICs for one VM
- **THEN** the system SHALL reject the inventory before OpenTofu apply
- **AND** it SHALL report the validation failure to the operator

#### Scenario: Validate manual VM ID ranges
- **WHEN** inventory declares template or VM IDs
- **THEN** the generator SHALL require manually declared IDs to be unique
- **AND** it SHALL validate template IDs in `9000-9500`, long-lived VM IDs in `1000-2000`, and ephemeral/lab VM IDs in `500-800`

### Requirement: OpenTofu-managed PVE VM lifecycle
The system SHALL use OpenTofu with the `bpg/proxmox` provider to manage new PVE VMs cloned from declared templates.

#### Scenario: Provision a VM with static cloud-init network configuration
- **WHEN** an operator declares a VM on one or more attachable logical networks with static IP addresses
- **THEN** OpenTofu SHALL create or update the VM from the declared template
- **AND** it SHALL configure hostname, static IP addresses, explicit default routes, DNS, and SSH access through cloud-init/OpenTofu initialization or runtime-rendered cloud-init snippets as appropriate
- **AND** it SHALL attach each declared VM NIC to the pre-existing bridge resolved from that NIC's logical network declaration
- **AND** it SHALL set declared deterministic MAC addresses on VM NICs when the VM uses explicit NIC declarations
- **AND** it SHALL use a full clone from the Packer-managed template

#### Scenario: Apply default VM hardware settings
- **WHEN** a VM omits optional hardware defaults
- **THEN** the system SHALL default to `2` CPU cores, `2048` MiB memory, `20` GiB root disk, CPU type `host`, BIOS `OVMF`, machine `q35`, `virtio-scsi-single`, root disk on `scsi0`, and qemu-guest-agent enabled
- **AND** VM-level declarations MAY override supported sizing and storage defaults

#### Scenario: Verify OVMF EFI disk support
- **WHEN** OVMF/q35 VM defaults are used
- **THEN** the implementation SHALL verify EFI disk support on the chosen datastore and provider configuration before first acceptance

#### Scenario: Protect long-lived VMs
- **WHEN** a VM is declared with a long-lived lifecycle class
- **THEN** the generated OpenTofu configuration or module behavior SHALL protect it from accidental destroy by default
- **AND** the VM SHALL default to boot on host startup
- **AND** destructive changes SHALL require an explicit operator decision outside normal VM creation flow

#### Scenario: Allow explicit ephemeral VM destruction
- **WHEN** a VM is declared with an ephemeral or lab lifecycle class
- **THEN** the generated OpenTofu configuration MAY allow destroy for that VM
- **AND** the VM SHALL NOT boot on host startup by default unless explicitly declared

#### Scenario: Keep existing VMs unmanaged by default
- **WHEN** the PVE automation foundation is introduced
- **THEN** existing PVE VMs SHALL NOT be imported, modified, renamed, or destroyed unless a later change explicitly scopes that migration

### Requirement: Existing PVE bridge network attachment
The system SHALL treat existing PVE host bridge configuration as a prerequisite and only manage VM NIC attachment to approved bridges.

#### Scenario: Attach a VM to the development network
- **WHEN** a VM or VM NIC declares `network: dev`
- **THEN** the generated OpenTofu input SHALL resolve the VM NIC bridge to the pre-existing development bridge such as `br_dev`
- **AND** it SHALL NOT attempt to create or modify `apps`, `apps.10`, or `br_dev` host network definitions

#### Scenario: Attach a VM to the production network
- **WHEN** a VM or VM NIC declares `network: prod`
- **THEN** the generated OpenTofu input SHALL resolve the VM NIC bridge to the pre-existing production bridge such as `br_prod`
- **AND** it SHALL NOT attempt to create or modify `apps`, `apps.50`, or `br_prod` host network definitions

#### Scenario: Attach multiple VM NICs to approved networks
- **WHEN** a VM declares multiple NICs on logical networks that are approved for VM attachment
- **THEN** the generated OpenTofu input SHALL attach one VM NIC per declaration
- **AND** each NIC SHALL use the bridge resolved from its logical network
- **AND** the system SHALL NOT create, update, or delete PVE host bridges, VLAN devices, SDN zones, OPNsense interfaces, firewall rules, or switch ports

#### Scenario: Reject non-VM networks by default
- **WHEN** a VM or VM NIC declares a network marked as not attachable for VMs, such as management or storage
- **THEN** the system SHALL reject the declaration unless an explicit future exception mechanism is defined

#### Scenario: Validate existing bridge presence separately
- **WHEN** operators run online PVE preflight checks
- **THEN** the system SHALL verify read-only that required bridges such as `br_dev` and `br_prod` exist on target nodes
- **AND** this online check SHALL be separate from offline validation that does not require PVE connectivity

### Requirement: Runtime cloud-init snippets are exact verified artifacts
The system SHALL render runtime cloud-init user-data and network-config snippets into local artifacts and verify that uploaded PVE snippets match those exact artifacts by checksum.

#### Scenario: Render snippets for an operation
- **WHEN** an operator renders runtime cloud-init snippets for declared PVE VMs
- **THEN** the system SHALL write user-data files for declared VMs to the ignored cloud-init cache directory
- **AND** it SHALL write network-config files for declared VMs that have at least one explicit NIC
- **AND** it SHALL write a manifest describing each rendered snippet file, VM identity, snippet kind, storage file ID, byte count, and SHA-256 checksum
- **AND** it SHALL treat the rendered files and manifest as the source of truth for later upload and verify steps in that operation
- **AND** it SHALL NOT write plaintext passwords, private keys, or token secrets into committed generated files

#### Scenario: Upload snippets from rendered artifacts
- **WHEN** an operator uploads runtime cloud-init snippets
- **THEN** the system SHALL upload the exact snippet file contents recorded in the local manifest
- **AND** it SHALL NOT implicitly re-render snippet content during upload
- **AND** it SHALL use the audited PVE host-side snippet wrapper rather than a broad remote install command

#### Scenario: Verify remote snippets by checksum
- **WHEN** an operator verifies runtime cloud-init snippets on a PVE node
- **THEN** the system SHALL compare each remote snippet with the SHA-256 checksum recorded in the local manifest
- **AND** verification SHALL fail when remote content differs from the manifest checksum, even if the remote file exists and contains valid YAML
- **AND** verification SHALL report which snippet failed without printing plaintext secrets, password hashes, private keys, or token material

#### Scenario: Preserve password hash runtime behavior
- **WHEN** runtime cloud-init snippets are rendered in separate operations
- **THEN** password hashes MAY differ because runtime password hashing may use fresh salt
- **AND** the system SHALL NOT require fixed long-lived salts or cross-operation password hash determinism
- **AND** upload and verify determinism SHALL be scoped to the exact artifacts rendered for the current operation

## ADDED Requirements

### Requirement: Multi-NIC cloud-init network configuration
The system SHALL generate cloud-init network-config for VMs that declare multiple NICs.

#### Scenario: Render MAC-matched network-config
- **WHEN** a VM declares multiple NICs
- **THEN** the rendered cloud-init network-config SHALL use network-config version 2
- **AND** each declared NIC SHALL be matched by its deterministic MAC address
- **AND** each declared NIC SHALL receive the declared stable interface name using `set-name`
- **AND** each declared NIC SHALL receive its declared static CIDR address

#### Scenario: Configure the default route
- **WHEN** a NIC declares `default_route: true`
- **THEN** the rendered network-config SHALL configure a default route through that NIC's gateway
- **AND** validation SHALL reject more than one `default_route: true` NIC for one VM

#### Scenario: Configure DNS for declared NICs
- **WHEN** a NIC declares DNS settings
- **THEN** rendered cloud-init network-config SHALL apply DNS settings on that NIC
- **AND** validation SHALL reject conflicting NIC metadata that cannot be rendered deterministically

#### Scenario: Use explicit Ansible connection metadata for generated inventory
- **WHEN** Ansible inventory is generated for a multi-NIC VM
- **THEN** `ansible_host` SHALL be the host address from the NIC with `ansible_connection: true`
- **AND** VMs without such a NIC SHALL NOT be emitted under `pve_vms`
- **AND** the generated inventory SHALL expose declared NIC metadata for later validation and bootstrap workflows

### Requirement: Multi-NIC validation rules
The system SHALL validate multi-NIC VM declarations before generated artifacts are accepted.

#### Scenario: Validate NIC identity
- **WHEN** a VM declares NICs
- **THEN** each NIC name SHALL be unique within the VM
- **AND** each NIC MAC address SHALL be globally unique across declared VMs
- **AND** each NIC static IP host address SHALL be globally unique across declared VMs

#### Scenario: Validate NIC networks
- **WHEN** a VM declares a NIC on a logical network
- **THEN** that logical network SHALL exist in cluster inventory
- **AND** the network SHALL be approved for VM attachment
- **AND** the NIC static IP SHALL be inside that network's CIDR and not equal to the network or broadcast address

#### Scenario: Validate generic NIC metadata
- **WHEN** a VM uses explicit NIC declarations
- **THEN** the VM SHALL allow zero or more NICs
- **AND** the VM SHALL allow zero or one `ansible_connection: true` NIC
- **AND** the VM SHALL allow zero or one `default_route: true` NIC
- **AND** the VM SHALL permit NIC roles such as `management`, `cluster`, `storage`, or `ingress` without requiring any specific one in the generic base model

#### Scenario: Reject invalid mixed declarations
- **WHEN** a VM declares both explicit `nics` and legacy top-level NIC fields
- **THEN** validation SHALL reject the declaration
- **AND** the failure message SHALL identify the deprecated top-level VM fields for operator correction
