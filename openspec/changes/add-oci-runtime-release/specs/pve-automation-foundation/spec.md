## MODIFIED Requirements

### Requirement: YAML source-of-truth for PVE VM automation
The system SHALL use the selected environment's operator-authored YAML inventory as the source of truth for PVE cluster defaults, networks, templates, PCI resource mappings, VMID policy, and VM declarations.

#### Scenario: Generate OpenTofu and Ansible inputs from one VM declaration
- **WHEN** an operator declares a VM with node, template, NICs, sizing, lifecycle, and Ansible group data in environment-owned YAML
- **THEN** the system SHALL generate OpenTofu provisioning input, Ansible inventory entries, and human-readable VM documentation from that declaration
- **AND** it SHALL avoid duplicate manual VM definitions in OpenTofu, Ansible, or current documentation

#### Scenario: Reject legacy top-level NIC fields
- **WHEN** an operator declares a VM using top-level `network`, `static_ip`, `gateway`, or `dns` fields
- **THEN** validation SHALL reject the declaration
- **AND** the error message SHALL point to the deprecated top-level fields

#### Scenario: Keep generated files reviewable and non-sensitive
- **WHEN** the generator emits outputs for an explicitly selected environment
- **THEN** it SHALL write `opentofu/pve.tfvars.json`, `ansible/pve.yml`, and `docs/pve-vms.md` beneath the explicitly selected generated-output directory
- **AND** those generated files SHALL NOT contain passwords, hashes, private keys, token secrets, or other secrets
- **AND** environment repositories committing generated outputs SHALL explicitly allow the intended non-sensitive outputs in their ignore rules
- **AND** validation SHALL detect when committed generated files are stale relative to source YAML

#### Scenario: Reject inconsistent source data before provisioning
- **WHEN** YAML contains duplicate IDs, hostnames, IPs, or MACs, unknown references, invalid NIC roles, conflicting routes, or contradictory declarations
- **THEN** validation SHALL fail before rendering, online access, planning, or mutation
- **AND** it SHALL report actionable inventory field context

#### Scenario: Validate manual VM ID ranges
- **WHEN** environment inventory declares template, long-lived, and ephemeral/lab VMID bands
- **THEN** validation SHALL require well-formed non-overlapping bands and unique IDs in the applicable band
- **AND** environment bands MAY narrow but SHALL NOT silently widen generic provider/PVE or destructive-operation safety limits
- **AND** reusable validation, rendering, and expectation code SHALL NOT require environment-specific bands

### Requirement: OpenTofu-managed PVE VM lifecycle
The system SHALL use OpenTofu with the `bpg/proxmox` provider to manage environment PVE VMs cloned from declared templates.

#### Scenario: Provision a VM with static cloud-init network configuration
- **WHEN** an operator declares a VM with attachable logical networks and static IP addresses
- **THEN** OpenTofu SHALL create or update the VM from the declared template
- **AND** it SHALL configure hostname, IPs, explicit default routes, DNS, and SSH access through declared initialization inputs
- **AND** each NIC SHALL use its declared logical network's existing bridge and deterministic MAC when declared
- **AND** clone behavior SHALL follow validated environment policy

#### Scenario: Apply default VM hardware settings
- **WHEN** a VM omits supported hardware settings
- **THEN** the system SHALL apply validated defaults from the selected environment inventory
- **AND** VM-level declarations MAY override supported defaults
- **AND** reusable automation SHALL NOT require environment-specific CPU, memory, disk, BIOS, machine, controller, NIC-count, pool, or clone-mode defaults

#### Scenario: Verify OVMF EFI disk support
- **WHEN** environment defaults use firmware or machine features that require datastore/provider support
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

### Requirement: PCIe passthrough declaration through PVE resource mappings
The system SHALL support VM PCIe passthrough by referencing environment PVE PCI resource mappings rather than raw PCI addresses in VM declarations.

#### Scenario: Attach the existing iGPU mapping to a VM
- **WHEN** a VM references a declared PCI mapping
- **THEN** generated OpenTofu SHALL render `hostpci` input using that mapping key and its validated defaults
- **AND** the VM declaration SHALL NOT hard-code a raw PCI path
- **AND** reusable automation SHALL NOT require a mapping named a fixed device mapping or any environment node name

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
- **WHEN** operators use the environment PVE environment root
- **THEN** OpenTofu state SHALL remain owned by the selected OpenTofu root/backend and excluded from Git
- **AND** documentation SHALL describe single-operator assumptions, backups, recovery, and a future remote-backend path

#### Scenario: Back up local state during helper operations
- **WHEN** a helper runs an apply-like OpenTofu operation
- **THEN** it SHALL back up local state under the selected ignored runtime backup directory
- **AND** legacy state and backups from before the repository cutover SHALL not be migrated or restored

#### Scenario: Preserve tool ownership boundaries
- **WHEN** PVE automation is documented
- **THEN** OpenTofu SHALL own VM lifecycle and hardware attachment, Ansible SHALL own guest configuration/verification, and Packer SHALL own reusable template construction
- **AND** PVE host networking, OPNsense, and switch mutation SHALL remain outside normal VM lifecycle operations

#### Scenario: Keep DNS management out of scope
- **WHEN** VMs are provisioned with static cloud-init IPs
- **THEN** the foundation SHALL NOT create or update DNS, DHCP, or host override records
- **AND** documentation SHALL state that name resolution requires manual work or a later automation change

### Requirement: Guest user and automation access model
The system SHALL derive guest users and the Ansible connection identity from the selected environment's validated inventory and consume caller-resolved credential variables.

#### Scenario: Render declared guest users
- **WHEN** cloud-init initializes a new VM
- **THEN** it SHALL render the declared users, sudo policies and supported cloud-init defaults
- **AND** it SHALL NOT require a particular personal user name or secret provider
- **AND** passwords and public keys SHALL come from the declared runtime environment variable names without entering committed generated files

#### Scenario: Connect Ansible through the declared automation user
- **WHEN** Ansible inventory is generated for managed VMs
- **THEN** it SHALL use `cluster.automation.ansible_user` and the validated become settings
- **AND** callers SHALL provide a matching guest account and the non-interactive privileges required by the selected operations
- **AND** generated inventory SHALL NOT contain passwords, private keys, token secrets or password hashes

### Requirement: 1Password runtime secret conventions
The system SHALL consume caller-supplied resolved credentials through documented environment variables or protected files. Callers MAY obtain them from 1Password or traditional Secret facilities. The IaaS runtime SHALL NOT retrieve secrets from 1Password or require its CLI or service account token. Reference metadata and item conventions are caller-owned.

#### Scenario: Reference caller-selected secret items
- **WHEN** an environment declares PVE or VM credential references
- **THEN** the caller SHALL select vault, item and field names according to the supported reference syntax
- **AND** runtime validation SHALL NOT require a fixed vault, personal identity or item name

#### Scenario: Generate password hashes at runtime
- **WHEN** cloud-init requires password hashes for VM users
- **THEN** the automation SHALL consume plaintext passwords supplied by the caller through the documented credential inputs
- **AND** it SHALL generate cloud-init-compatible password hashes during execution
- **AND** it SHALL NOT write plaintext passwords or generated password hashes into committed generated files

#### Scenario: Inject secrets through op run
- **WHEN** Packer or OpenTofu commands require secrets
- **THEN** the caller MAY use `op run` with a reference-only template to resolve environment-selected `op://...` references before invoking IaaS
- **AND** IaaS SHALL receive resolved environment variables or protected files without invoking `op`
- **AND** committed env templates SHALL NOT contain secret values

#### Scenario: Use a caller-selected vault without changing the runtime
- **WHEN** an environment supplies valid supported references to another vault
- **THEN** the caller SHALL resolve its selected references and IaaS SHALL consume the supplied credentials without substituting environment defaults
- **AND** offline checks SHALL validate references without resolving them
- **AND** CI callers choosing 1Password SHALL own a separately configured noninteractive identity and its token, without requiring a developer desktop login
- **AND** callers choosing traditional Secrets SHALL NOT require a 1Password identity

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
- **AND** SSH authentication SHALL use the caller-supplied key for the dedicated automation identity
- **AND** the SSH identity SHALL use limited `NOPASSWD` sudo based on spike results rather than broad `NOPASSWD: ALL`

#### Scenario: Deploy the audited PVE host wrapper
- **WHEN** the PVE node bootstrap playbook runs
- **THEN** it SHALL copy `automation/pve-node/bin/iaas-pve-template-build` to `/usr/local/sbin/iaas-pve-template-build`
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
- **THEN** operators SHALL create `pve-ops@pve`, create the `opentofu` API token, assign initial role/ACLs, and make the credentials available through caller-owned environment injection or protected files before OpenTofu runs
- **AND** the initial environment-selected ACL SHALL be assigned to both `pve-ops@pve` and `pve-ops@pve!opentofu` for PVE 9 privilege-separated token compatibility
- **AND** the initial environment-selected role SHALL include `SDN.Use` when VM bridges are checked through PVE SDN paths
- **AND** the OpenTofu configuration that consumes `pve-ops@pve!opentofu` SHALL NOT manage that same API user, token, or initial ACL root of trust in this foundation

#### Scenario: Document PVE identity bootstrap
- **WHEN** the PVE automation foundation is documented
- **THEN** documentation SHALL include a bootstrap runbook for creating `pve-ops@pve`, creating `pve-ops@pve!opentofu`, creating `pve-ops@pve!packer`, assigning initial role/ACLs, and supplying the resulting credentials through either caller-side 1Password injection or traditional Secrets
- **AND** it SHALL state that future automation of this bootstrap may be introduced separately under an existing administrator identity

#### Scenario: Use generic host helper paths
- **WHEN** PVE helper source assets, bootstrap declarations, preflight or runtime callers select helper paths
- **THEN** the canonical names SHALL be `iaas-pve-template-build` and `iaas-pve-snippet-upload`, with matching sudoers and generic execution variables
- **AND** changing names SHALL preserve argument validation, dedicated identities, wrapper-only permissions and mutual exclusion
- **AND** existing hosts SHALL require an explicit documented cutover before new callers run, without silent old-name fallback or simultaneous old/new lock domains

### Requirement: Reserved naming and ID ranges
The system SHALL validate environment-declared PVE naming and VMID policies against generic safety constraints.

#### Scenario: Reserve VM ID ranges
- **WHEN** environment inventory defines template, long-lived, and ephemeral/lab VMID bands
- **THEN** each band SHALL be well formed, non-overlapping, and within generic PVE/provider safety limits
- **AND** VMs and templates SHALL use the band matching their declared lifecycle
- **AND** destructive wrappers SHALL enforce absolute protection limits in addition to environment policy

#### Scenario: Name templates safely and predictably
- **WHEN** an environment declares a reusable template
- **THEN** the name SHALL use a validated conservative PVE-safe pattern
- **AND** date or version naming MAY be declared by environment policy
- **AND** automation SHALL NOT require an environment-specific template name
