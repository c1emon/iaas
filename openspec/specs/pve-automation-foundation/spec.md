# pve-automation-foundation Specification

## Purpose

Provide a safe PVE automation foundation for declarative VM inventory, Debian 13 template construction, OpenTofu-managed VM lifecycle, generated Ansible inventory, and guardrails around host networking, local state, secrets, and PCIe passthrough.

## Requirements

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

### Requirement: Runtime cloud-init snippets are exact verified artifacts
The system SHALL render runtime cloud-init user-data and network-config snippets into local artifacts and verify that uploaded PVE snippets match those exact artifacts by checksum.

#### Scenario: Render snippets for an operation
- **WHEN** an operator renders runtime cloud-init snippets for declared PVE VMs
- **THEN** the system SHALL write user-data files for declared VMs to the ignored cloud-init cache directory
- **AND** it SHALL write network-config files for declared VMs that have at least one NIC
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
- **THEN** each NIC name SHALL be unique within the VM and a lower-case DNS-label-safe Linux interface name of at most 15 characters
- **AND** each NIC MAC address SHALL be globally unique across declared VMs
- **AND** each NIC static IP host address SHALL be globally unique across declared VMs

#### Scenario: Reject a NIC name that cannot be rendered by Linux
- **WHEN** a VM NIC name contains more than 15 characters
- **THEN** offline inventory validation SHALL reject the declaration before generating cloud-init network-config
- **AND** the validation error SHALL identify the NIC name field and its 15-character limit

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

#### Scenario: Preserve password hash runtime behavior
- **WHEN** runtime cloud-init snippets are rendered in separate operations
- **THEN** password hashes MAY differ because runtime password hashing may use fresh salt
- **AND** the system SHALL NOT require fixed long-lived salts or cross-operation password hash determinism
- **AND** upload and verify determinism SHALL be scoped to the exact artifacts rendered for the current operation

### Requirement: Runtime cloud-init SSH operations are bounded
The system SHALL bound SSH subprocesses used for runtime cloud-init upload and verification.

#### Scenario: SSH upload or verify hangs
- **WHEN** a cloud-init upload or verify SSH subprocess exceeds the configured timeout
- **THEN** the command SHALL fail with an operator-readable error
- **AND** it SHALL NOT hang indefinitely
- **AND** it SHALL NOT disclose runtime secret values in the timeout error

### Requirement: PVE snippet wrapper supports checksum verification
The PVE host-side snippet wrapper SHALL support verifying stored snippet content against an expected SHA-256 checksum.

#### Scenario: Wrapper verifies matching checksum
- **WHEN** the wrapper is invoked for an existing snippet with verify mode and the expected SHA-256 checksum
- **THEN** it SHALL read the stored snippet from the constrained storage path
- **AND** it SHALL exit successfully when the stored content checksum matches the expected value

#### Scenario: Wrapper detects checksum mismatch
- **WHEN** the wrapper is invoked for an existing snippet with verify mode and an expected SHA-256 checksum that does not match the stored content
- **THEN** it SHALL fail with an operator-readable checksum mismatch error
- **AND** it SHALL NOT rewrite, delete, or otherwise mutate the stored snippet during verification

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

### Requirement: Stable offline inventory validation boundary
The system SHALL keep offline PVE inventory validation as a stable boundary that can be refactored internally without changing operator-facing validation commands or generated artifacts.

#### Scenario: Refactor validation internals without operator workflow changes
- **WHEN** the implementation splits validation code into separate modules
- **THEN** existing validation and generation commands SHALL continue to work with the same inputs
- **AND** committed generated artifacts SHALL remain unchanged when source YAML is unchanged
- **AND** online PVE checks SHALL remain separate from offline validation

### Requirement: Protected and unprotected VM resource parity
The PVE cloud-init VM module SHALL keep its protected and unprotected VM resource definitions structurally equivalent except for the minimal differences required to select and protect the lifecycle branch.

#### Scenario: Module selects the protected resource
- **WHEN** VM lifecycle policy enables destroy protection
- **THEN** the protected resource SHALL have count `1` and the unprotected resource SHALL have count `0`
- **AND** the protected resource SHALL declare literal `lifecycle.prevent_destroy = true`

#### Scenario: Module selects the unprotected resource
- **WHEN** VM lifecycle policy disables destroy protection
- **THEN** the unprotected resource SHALL have count `1` and the protected resource SHALL have count `0`
- **AND** the unprotected resource SHALL NOT declare `lifecycle.prevent_destroy`

#### Scenario: Common VM behavior is edited
- **WHEN** a common resource argument, nested block, ignore rule, precondition, or other VM behavior changes
- **THEN** the protected and unprotected resource definitions SHALL remain identical for that behavior
- **AND** the only permitted structural differences SHALL be the resource labels, complementary count expressions, and protected-only literal `prevent_destroy = true`

### Requirement: Offline VM resource parity guard
The repository SHALL enforce protected/unprotected VM resource parity through a fail-closed offline structural check.

#### Scenario: Resource definitions remain in parity
- **WHEN** the parity guard normalizes only the explicitly permitted differences
- **THEN** the remaining protected and unprotected resource definitions SHALL compare equal
- **AND** the guard SHALL pass without provider credentials, PVE access, OpenTofu plan, state access, or mutation

#### Scenario: One resource drifts
- **WHEN** either resource differs in an argument, nested block, lifecycle ignore rule, precondition, or other content outside the explicit allowlist
- **THEN** the parity guard SHALL fail
- **AND** it SHALL report an actionable normalized diff identifying the one-sided change

#### Scenario: Guard structure is missing or ambiguous
- **WHEN** either expected resource/guard marker is missing, duplicated, misordered, or cannot be normalized using the exact permitted-difference rules
- **THEN** the parity guard SHALL fail rather than skip or broaden its comparison

#### Scenario: Root aggregate offline validation runs
- **WHEN** an operator or CI runs the root aggregate offline check
- **THEN** it SHALL execute the VM resource parity guard through the existing repository test path
- **AND** the guard SHALL NOT rewrite HCL or change OpenTofu state

### Requirement: Intentional duplication is documented and preserved
The module SHALL document why the two VM resources remain separate and how their parity is maintained.

#### Scenario: Maintainer reviews the duplicated resources
- **WHEN** a maintainer opens the PVE cloud-init VM module
- **THEN** source comments SHALL explain that lifecycle destroy protection requires a static resource-level declaration
- **AND** the comments SHALL identify the exact allowed differences and the offline parity guard

#### Scenario: Maintainer considers merging the resources
- **WHEN** a future refactor proposes removing the duplicated resources or changing their addresses
- **THEN** that work SHALL require a separate reviewed change with explicit state-migration and lifecycle-safety analysis
- **AND** this parity change SHALL NOT perform that refactor

### Requirement: Template-derived VM architecture fact
The system SHALL treat guest CPU architecture as a generic VM/template fact and
SHALL NOT require workload overlays to restate it. The first implementation
SHALL support canonical `amd64`.

#### Scenario: VM inventory is normalized and rendered
- **WHEN** a VM references a template declaring canonical `amd64`
- **THEN** the normalized VM SHALL inherit that canonical template architecture
- **AND** generated Ansible host variables SHALL expose it as `pve_architecture`
- **AND** existing generated host facts and PVE lifecycle meanings SHALL remain unchanged

#### Scenario: Template architecture is invalid
- **WHEN** a referenced template omits architecture, uses a runtime alias such as `x86_64`, or declares another unsupported value
- **THEN** PVE inventory validation SHALL fail before OpenTofu, Ansible, documentation, or Packer outputs are accepted

#### Scenario: Workload consumes VM architecture
- **WHEN** K3s or another workload composes its intent with generated VM facts
- **THEN** it SHALL select architecture-specific behavior from `pve_architecture`
- **AND** it SHALL reject any workload-level per-node architecture override
