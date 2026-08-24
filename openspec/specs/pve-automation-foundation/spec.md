# pve-automation-foundation Specification

## Purpose

Provide a safe PVE automation foundation for declarative VM inventory, Debian 13 template construction, OpenTofu-managed VM lifecycle, generated Ansible inventory, and guardrails around host networking, local state, secrets, and PCIe passthrough.

## Requirements

### Requirement: YAML source-of-truth for PVE VM automation
The system SHALL use operator-authored YAML inventory as the source of truth for PVE cluster defaults, networks, templates, PCI resource mappings, and VM declarations.

#### Scenario: Generate OpenTofu and Ansible inputs from one VM declaration
- **WHEN** an operator declares a VM with node, template, NICs, sizing, lifecycle, and Ansible group data in YAML
- **THEN** the system SHALL generate OpenTofu input for VM provisioning from that declaration
- **AND** it SHALL generate Ansible inventory entries from the same declaration
- **AND** it SHALL generate human-readable VM documentation from the same declaration
- **AND** it SHALL avoid requiring duplicate manual VM definitions in OpenTofu and Ansible

#### Scenario: Reject legacy top-level NIC fields
- **WHEN** an operator declares a VM using top-level `network`, `static_ip`, `gateway`, or `dns` fields
- **THEN** validation SHALL reject the declaration
- **AND** the error message SHALL point to the deprecated top-level fields

#### Scenario: Keep generated files reviewable and non-sensitive
- **WHEN** the generator emits OpenTofu, Ansible, or documentation outputs
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
- **AND** replacement of an existing template SHALL require explicit force mode constrained to template VM IDs `9000-9500` and conservative PVE-safe template names

#### Scenario: Spike the genericcloud import path first
- **WHEN** implementation starts
- **THEN** the project SHALL first validate the Debian 13 genericcloud-to-PVE-template route before building the full Packer implementation
- **AND** it SHALL record the selected route and fallback considerations in the design/runbook

### Requirement: OpenTofu-managed PVE VM lifecycle
The system SHALL use OpenTofu with the `bpg/proxmox` provider to manage new PVE VMs cloned from declared templates.

#### Scenario: Provision a VM with static cloud-init network configuration
- **WHEN** an operator declares a VM with one or more attachable logical networks and static IP addresses
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

### Requirement: PCIe passthrough declaration through PVE resource mappings
The system SHALL support VM PCIe passthrough declarations by referencing existing PVE PCI resource mappings rather than raw PCI addresses.

#### Scenario: Attach the existing iGPU mapping to a VM
- **WHEN** a VM declares a passthrough PCI device using mapping `iGpu0`
- **THEN** the generated OpenTofu VM configuration SHALL render a `hostpci` attachment that references the `iGpu0` mapping
- **AND** it SHALL NOT hard-code a raw PCI path such as `0000:00:02.1` in the VM declaration

#### Scenario: Validate passthrough node compatibility
- **WHEN** a VM declares a PCI mapping
- **THEN** the system SHALL validate that the VM's selected PVE node is listed as an allowed node for that mapping
- **AND** it SHALL reject the declaration before provisioning if the mapping is unavailable on the selected node

#### Scenario: Keep passthrough HA disabled
- **WHEN** a VM declares PCIe passthrough
- **THEN** the system SHALL require HA to be disabled for that VM in this foundation
- **AND** it SHALL document migration and HA limitations for passthrough VMs

#### Scenario: Restrict passthrough schema to core fields
- **WHEN** a VM declares PCIe passthrough in the first implementation
- **THEN** the declaration SHALL support `device`, `mapping`, `pcie`, `rombar`, and `xvga`
- **AND** automatic node changes or migration SHALL be rejected for passthrough VMs

#### Scenario: Defer passthrough from first acceptance
- **WHEN** the first disposable dev VM acceptance is executed
- **THEN** PCIe passthrough SHALL NOT be required for that acceptance path
- **AND** passthrough support SHALL be validated separately after core VM provisioning succeeds

### Requirement: Local state and safety documentation
The system SHALL start with local OpenTofu state and document the operational assumptions and safety constraints of that choice.

#### Scenario: Use local state safely for initial operation
- **WHEN** operators use the initial PVE automation foundation
- **THEN** OpenTofu state SHALL be local at `infra/tofu/pve/terraform.tfstate` and excluded from Git
- **AND** documentation SHALL describe single-operator assumptions, state backup expectations, and a future remote backend migration path

#### Scenario: Back up local state during helper operations
- **WHEN** Makefile or helper targets run apply-like OpenTofu operations
- **THEN** they SHALL back up local state to a timestamped path under `.cache/tofu-state-backups/` before and/or after the operation

#### Scenario: Preserve tool ownership boundaries
- **WHEN** PVE VM automation is documented
- **THEN** documentation SHALL state that OpenTofu owns VM lifecycle and VM hardware attachment
- **AND** Ansible owns guest OS configuration and verification
- **AND** Packer owns reusable template creation
- **AND** existing OPNsense, switch, and PVE host network automation remains outside this foundation unless explicitly introduced by later changes

#### Scenario: Keep DNS management out of scope
- **WHEN** VMs are provisioned with static cloud-init IPs
- **THEN** this foundation SHALL NOT create or update OPNsense DNS, DHCP, or host override records
- **AND** documentation SHALL state that hostname/FQDN resolution may require manual DNS work or a later DNS automation change

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
- **AND** it SHALL NOT contain sudo passwords, login passwords, private keys, token secrets, or password hashes

#### Scenario: Disable direct root SSH by default
- **WHEN** cloud-init configures SSH access for a new VM
- **THEN** direct root SSH login SHALL be disabled by default
- **AND** SSH access SHALL use key-based authentication supplied at runtime through 1Password SSH Agent or the local SSH agent
- **AND** SSH password authentication SHALL be disabled by default

#### Scenario: Avoid first-boot package upgrades
- **WHEN** cloud-init initializes a new VM
- **THEN** it SHALL NOT run package update or package upgrade by default
- **AND** package maintenance SHALL be owned by Packer template rebuilds and Ansible baseline workflows

#### Scenario: Render and retain runtime cloud-init snippets
- **WHEN** Section 4A renders cloud-init user-data for a VM
- **THEN** the helper SHALL create a snippet in shared `images` storage using a stable `opentofu-vm-<vmid>-user-data.yml` name
- **AND** OpenTofu SHALL reference that snippet via `user_data_file_id`
- **AND** the snippet SHALL remain available for the VM lifetime instead of being deleted immediately after upload
- **AND** snippet upload SHALL use the audited host-side wrapper rather than a broad `sudo install` path

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
The system SHALL use the `Astra` 1Password vault as the runtime source for infrastructure secrets.

#### Scenario: Reference standardized 1Password items
- **WHEN** automation needs PVE or VM credentials
- **THEN** it SHALL use short kebab-case item names under the `Astra` vault
- **AND** the initial item names SHALL include `pve-opentofu-api-token`, `pve-packer-api-token`, `pve-ssh-automation-user`, `vm-user-clemon`, and `vm-user-ops`
- **AND** fields SHALL use snake_case names such as `username`, `password`, `public_key`, `private_key`, `token_id`, `token_secret`, `api_token`, and `endpoint`

#### Scenario: Generate password hashes at runtime
- **WHEN** cloud-init requires password hashes for VM users
- **THEN** the automation SHALL retrieve plaintext passwords from 1Password at runtime
- **AND** it SHALL generate cloud-init-compatible password hashes during execution
- **AND** it SHALL NOT write plaintext passwords or generated password hashes into committed generated files

#### Scenario: Inject secrets through op run
- **WHEN** Packer or OpenTofu commands require secrets
- **THEN** the runtime wrapper SHALL use `op run` with environment variables sourced from a committed template containing `op://Astra/...` references
- **AND** committed env templates SHALL NOT contain secret values

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
- **THEN** it SHALL copy `infra/pve-node/bin/astra-pve-template-build` to `/usr/local/sbin/astra-pve-template-build`
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
The system SHALL enforce reserved VM ID ranges and conservative template naming rules for PVE automation.

#### Scenario: Reserve VM ID ranges
- **WHEN** inventory declares templates or VMs
- **THEN** template IDs SHALL be in `9000-9500`
- **AND** long-lived VM IDs SHALL be in `1000-2000`
- **AND** ephemeral or lab VM IDs SHALL be in `500-800`

#### Scenario: Name templates safely and predictably
- **WHEN** a Debian 13 template is built
- **THEN** the initial inventory SHOULD use the naming pattern `debian-13-tmpl-{date}`
- **AND** the reusable template build wrapper SHALL accept conservative PVE-safe inventory-declared names rather than hard-coding a Debian-only prefix
- **AND** the source Debian 13 genericcloud image URL and checksum SHALL be pinned at implementation time after selecting the current latest image

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
