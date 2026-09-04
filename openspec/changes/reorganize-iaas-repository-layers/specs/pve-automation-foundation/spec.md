## MODIFIED Requirements

### Requirement: YAML source-of-truth for PVE VM automation
The system SHALL use Astra's operator-authored YAML inventory as the source of truth for PVE cluster defaults, networks, templates, PCI resource mappings, VMID policy, and VM declarations.

#### Scenario: Generate OpenTofu and Ansible inputs from one VM declaration
- **WHEN** an operator declares a VM with node, template, NICs, sizing, lifecycle, and Ansible group data in Astra YAML
- **THEN** the system SHALL generate OpenTofu provisioning input, Ansible inventory entries, and human-readable VM documentation from that declaration
- **AND** it SHALL avoid duplicate manual VM definitions in OpenTofu, Ansible, or current documentation

#### Scenario: Reject legacy top-level NIC fields
- **WHEN** an operator declares a VM using top-level `network`, `static_ip`, `gateway`, or `dns` fields
- **THEN** validation SHALL reject the declaration
- **AND** the error message SHALL point to the deprecated top-level fields

#### Scenario: Keep generated files reviewable and non-sensitive
- **WHEN** the generator emits Astra outputs
- **THEN** it SHALL write `environments/astra/generated/opentofu/pve.tfvars.json`, `environments/astra/generated/ansible/pve.yml`, and `environments/astra/generated/docs/pve-vms.md`
- **AND** those committed files SHALL NOT contain passwords, hashes, private keys, token secrets, or other secrets
- **AND** ignore rules SHALL explicitly allow intended committed outputs
- **AND** validation SHALL detect when committed generated files are stale relative to source YAML

#### Scenario: Reject inconsistent source data before provisioning
- **WHEN** YAML contains duplicate IDs, hostnames, IPs, or MACs, unknown references, invalid NIC roles, conflicting routes, or contradictory declarations
- **THEN** validation SHALL fail before rendering, online access, planning, or mutation
- **AND** it SHALL report actionable inventory field context

#### Scenario: Validate manual VM ID ranges
- **WHEN** environment inventory declares template, long-lived, and ephemeral/lab VMID bands
- **THEN** validation SHALL require well-formed non-overlapping bands and unique IDs in the applicable band
- **AND** environment bands MAY narrow but SHALL NOT silently widen generic provider/PVE or destructive-operation safety limits
- **AND** reusable validation, rendering, and expectation code SHALL NOT require Astra-specific bands

### Requirement: Debian 13 PVE template build foundation
The system SHALL define a Packer-based process for building a Debian 13 cloud-init-capable PVE template before creating VMs from that template.

#### Scenario: Build a reusable Debian 13 template
- **WHEN** an operator runs the documented Packer build with required PVE connection and storage variables
- **THEN** the build SHALL produce a Debian 13 PVE template suitable for cloud-init cloning
- **AND** the template SHALL include cloud-init and qemu-guest-agent readiness
- **AND** the template SHALL use a pinned Debian 13 genericcloud image URL and checksum selected at implementation time
- **AND** the template SHALL include configured apt mirrors, timezone, locale, and build bridge parameters sourced from inventory-driven template build settings
- **AND** the template SHALL be cleaned of machine-specific identity, SSH host keys, cloud-init state, and temporary build artifacts before reuse

#### Scenario: Keep VM-specific data out of the template
- **WHEN** the Debian 13 template is built
- **THEN** the template SHALL NOT contain fixed VM hostnames, fixed VM IP addresses, VM-specific SSH host keys, or application-specific secrets

#### Scenario: Retain existing templates by default
- **WHEN** a new Debian 13 template is built
- **THEN** existing dated templates SHALL be retained by default for rollback
- **AND** replacement of an existing template SHALL require explicit force mode constrained by both the inventory-declared template VMID band and the existing host-side wrapper protection envelope

#### Scenario: Spike the genericcloud import path first
- **WHEN** implementation starts
- **THEN** the project SHALL first validate the Debian 13 genericcloud-to-PVE-template route before building the full Packer implementation
- **AND** it SHALL record the selected route and fallback considerations in the design/runbook

### Requirement: OpenTofu-managed PVE VM lifecycle
The system SHALL use OpenTofu with the `bpg/proxmox` provider to manage Astra PVE VMs cloned from declared templates.

#### Scenario: Provision a VM with static cloud-init network configuration
- **WHEN** an operator declares a VM with attachable logical networks and static IP addresses
- **THEN** OpenTofu SHALL create or update the VM from the declared template
- **AND** it SHALL configure hostname, IPs, explicit default routes, DNS, and SSH access through declared initialization inputs
- **AND** each NIC SHALL use its declared logical network's existing bridge and deterministic MAC when declared
- **AND** clone behavior SHALL follow validated environment policy

#### Scenario: Apply default VM hardware settings
- **WHEN** a VM omits supported hardware settings
- **THEN** the system SHALL apply validated defaults from the Astra inventory
- **AND** VM-level declarations MAY override supported defaults
- **AND** reusable automation SHALL NOT require Astra-specific CPU, memory, disk, BIOS, machine, controller, NIC-count, pool, or clone-mode defaults

#### Scenario: Verify OVMF EFI disk support
- **WHEN** Astra defaults use firmware or machine features that require datastore/provider support
- **THEN** implementation SHALL validate the required support before first acceptance

#### Scenario: Protect long-lived VMs
- **WHEN** a VM is declared with a long-lived lifecycle class
- **THEN** generated OpenTofu behavior SHALL protect it from accidental destroy by default
- **AND** boot-on-host-start and destructive-change behavior SHALL follow validated lifecycle policy
- **AND** destructive changes SHALL require an explicit operator decision outside normal creation flow

#### Scenario: Allow explicit ephemeral VM destruction
- **WHEN** a VM is declared with an ephemeral or lab lifecycle class
- **THEN** generated behavior MAY allow destroy for that VM
- **AND** boot-on-host-start SHALL follow declared environment policy rather than a hidden code default

#### Scenario: Keep existing VMs unmanaged by default
- **WHEN** an environment root is selected
- **THEN** existing PVE VMs SHALL NOT be imported, modified, renamed, or destroyed unless an explicit later operation scopes that ownership transition

### Requirement: Existing PVE bridge network attachment
The system SHALL treat existing PVE host bridge configuration as a prerequisite and only manage VM NIC attachment to inventory-declared attachable networks.

#### Scenario: Attach a VM to the development network
- **WHEN** a VM NIC references a logical network marked attachable for VMs
- **THEN** generated OpenTofu input SHALL resolve the NIC bridge from that network declaration
- **AND** it SHALL NOT create or modify host bridge, VLAN, or physical interface definitions

#### Scenario: Attach a VM to the production network
- **WHEN** a VM NIC references another logical network marked attachable for VMs
- **THEN** generated OpenTofu input SHALL resolve the NIC bridge from that network declaration
- **AND** reusable automation SHALL NOT require a network named `prod` or a bridge named `br_prod`
- **AND** it SHALL NOT create or modify host bridge, VLAN, or physical interface definitions

#### Scenario: Attach multiple VM NICs to approved networks
- **WHEN** a VM declares multiple NICs on attachable logical networks
- **THEN** generated input SHALL attach one NIC per declaration using the declared bridge
- **AND** the system SHALL NOT create, update, or delete PVE host bridges, VLAN devices, SDN zones, OPNsense interfaces, firewall rules, or switch ports

#### Scenario: Reject non-VM networks by default
- **WHEN** a VM NIC references a network not approved for VM attachment
- **THEN** validation SHALL reject it unless a separately specified exception mechanism exists

#### Scenario: Validate existing bridge presence separately
- **WHEN** operators run online PVE preflight
- **THEN** it SHALL verify read-only that all inventory-required bridges exist on target nodes
- **AND** the online check SHALL remain separate from offline validation

### Requirement: PCIe passthrough declaration through PVE resource mappings
The system SHALL support VM PCIe passthrough by referencing Astra PVE PCI resource mappings rather than raw PCI addresses in VM declarations.

#### Scenario: Attach the existing iGPU mapping to a VM
- **WHEN** a VM references a declared PCI mapping
- **THEN** generated OpenTofu SHALL render `hostpci` input using that mapping key and its validated defaults
- **AND** the VM declaration SHALL NOT hard-code a raw PCI path
- **AND** reusable automation SHALL NOT require a mapping named `iGpu0` or any Astra node name

#### Scenario: Validate passthrough node compatibility
- **WHEN** a VM declares a PCI mapping
- **THEN** validation SHALL require its selected node to be allowed by that mapping
- **AND** it SHALL fail before provisioning when the mapping is unavailable

#### Scenario: Keep passthrough HA disabled
- **WHEN** a VM declares PCI passthrough
- **THEN** validation SHALL apply the mapping's declared HA capability and generic migration limitations
- **AND** environment policy SHALL NOT bypass absolute passthrough safety constraints

#### Scenario: Restrict passthrough schema to core fields
- **WHEN** a VM declares PCI passthrough
- **THEN** it SHALL use only the supported core device, mapping, and provider flag fields
- **AND** automatic node changes or migration SHALL be rejected when incompatible with declared mappings

#### Scenario: Defer passthrough from first acceptance
- **WHEN** basic disposable VM acceptance is executed
- **THEN** PCI passthrough SHALL NOT be required for that path
- **AND** passthrough SHALL be validated separately after core provisioning succeeds

### Requirement: Local state and safety documentation
The system SHALL keep future local OpenTofu state ignored and document its operational safety constraints.

#### Scenario: Use local state safely for initial operation
- **WHEN** operators use the Astra PVE environment root
- **THEN** OpenTofu state SHALL remain local under `environments/astra/opentofu/pve/` and excluded from Git
- **AND** documentation SHALL describe single-operator assumptions, backups, recovery, and a future remote-backend path

#### Scenario: Back up local state during helper operations
- **WHEN** a helper runs an apply-like OpenTofu operation
- **THEN** it SHALL back up future Astra state under the existing ignored state-backup location
- **AND** legacy state and backups from before the repository cutover SHALL not be migrated or restored

#### Scenario: Preserve tool ownership boundaries
- **WHEN** PVE automation is documented
- **THEN** OpenTofu SHALL own VM lifecycle and hardware attachment, Ansible SHALL own guest configuration/verification, and Packer SHALL own reusable template construction
- **AND** PVE host networking, OPNsense, and switch mutation SHALL remain outside normal VM lifecycle operations

#### Scenario: Keep DNS management out of scope
- **WHEN** VMs are provisioned with static cloud-init IPs
- **THEN** the foundation SHALL NOT create or update DNS, DHCP, or host override records
- **AND** documentation SHALL state that name resolution requires manual work or a later automation change

### Requirement: Separate PVE API and SSH automation identities
The system SHALL use separate dedicated identities for PVE API automation and PVE node SSH automation.

#### Scenario: Use PVE realm identity for API automation
- **WHEN** PVE automation credentials are configured for the initial implementation
- **THEN** the PVE API user SHALL be `pve-ops@pve`
- **AND** the OpenTofu API token SHALL be `pve-ops@pve!opentofu`
- **AND** the Packer API token SHALL be `pve-ops@pve!packer`
- **AND** PVE API permissions SHALL be assigned to the dedicated API identity rather than to `root@pam` or a personal human user

#### Scenario: Use Linux node identity for SSH automation
- **WHEN** Packer or provider behavior requires SSH access to PVE nodes
- **THEN** the PVE node SSH user SHALL be `pve-ops`
- **AND** the SSH user SHALL be provisioned consistently on each node that automation needs to access
- **AND** SSH authentication SHALL use the key managed by the `pve-ssh-automation-user` 1Password item
- **AND** the SSH identity SHALL use limited `NOPASSWD` sudo based on spike results rather than broad `NOPASSWD: ALL`

#### Scenario: Deploy the audited PVE host wrapper
- **WHEN** the PVE node bootstrap playbook runs
- **THEN** it SHALL copy `automation/pve-node/bin/astra-pve-template-build` to `/usr/local/sbin/astra-pve-template-build`
- **AND** the installed wrapper SHALL be owned by `root:root` with mode `0750`
- **AND** the bootstrap SHALL validate the installed wrapper and sudoers file without mutating system state
- **AND** the default sudoers policy SHALL be wrapper-only for `pve-ops`
- **AND** a variable override MAY temporarily allow a broader preflight sudo allowlist

#### Scenario: Keep global PVE SSHD policy out of scope
- **WHEN** the PVE node bootstrap extension is implemented
- **THEN** it SHALL NOT modify global PVE node SSHD policy such as password authentication or daemon configuration
- **AND** SSH policy hardening SHALL remain a manual prerequisite handled separately

#### Scenario: Avoid root and personal automation identities
- **WHEN** OpenTofu, Packer, or provider SSH access authenticates to PVE
- **THEN** it SHALL use dedicated `pve-ops@pve` API or `pve-ops` SSH automation identities by default
- **AND** it SHALL NOT use `root@pam` or a personal human user as the default automation identity

#### Scenario: Bootstrap PVE API identity outside OpenTofu
- **WHEN** the initial PVE automation identity is prepared
- **THEN** operators SHALL create `pve-ops@pve`, create the `opentofu` API token, assign initial role/ACLs, and populate 1Password before OpenTofu runs
- **AND** the initial `AstraAutomation` ACL SHALL be assigned to both `pve-ops@pve` and `pve-ops@pve!opentofu` for PVE 9 privilege-separated token compatibility
- **AND** the initial `AstraAutomation` role SHALL include `SDN.Use` when VM bridges are checked through PVE SDN paths
- **AND** the OpenTofu configuration that consumes `pve-ops@pve!opentofu` SHALL NOT manage that same API user, token, or initial ACL root of trust in this foundation

#### Scenario: Document PVE identity bootstrap
- **WHEN** the PVE automation foundation is documented
- **THEN** documentation SHALL include a bootstrap runbook for creating `pve-ops@pve`, creating `pve-ops@pve!opentofu`, creating `pve-ops@pve!packer`, assigning initial role/ACLs, and filling the related 1Password API token items
- **AND** it SHALL state that future automation of this bootstrap may be introduced separately under an existing administrator identity

### Requirement: Reserved naming and ID ranges
The system SHALL validate environment-declared PVE naming and VMID policies against generic safety constraints.

#### Scenario: Reserve VM ID ranges
- **WHEN** environment inventory defines template, long-lived, and ephemeral/lab VMID bands
- **THEN** each band SHALL be well formed, non-overlapping, and within generic PVE/provider safety limits
- **AND** VMs and templates SHALL use the band matching their declared lifecycle
- **AND** destructive wrappers SHALL enforce absolute protection limits in addition to Astra policy

#### Scenario: Name templates safely and predictably
- **WHEN** an environment declares a reusable template
- **THEN** the name SHALL use a validated conservative PVE-safe pattern
- **AND** date or version naming MAY be declared by environment policy
- **AND** automation SHALL NOT require an Astra-specific template name
