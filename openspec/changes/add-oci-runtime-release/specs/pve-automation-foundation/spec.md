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
- **AND** reusable validation, rendering, and expectation code SHALL NOT require Astra-specific bands

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
- **THEN** operators SHALL create `pve-ops@pve`, create the `opentofu` API token, assign initial role/ACLs, and populate 1Password before OpenTofu runs
- **AND** the initial `AstraAutomation` ACL SHALL be assigned to both `pve-ops@pve` and `pve-ops@pve!opentofu` for PVE 9 privilege-separated token compatibility
- **AND** the initial `AstraAutomation` role SHALL include `SDN.Use` when VM bridges are checked through PVE SDN paths
- **AND** the OpenTofu configuration that consumes `pve-ops@pve!opentofu` SHALL NOT manage that same API user, token, or initial ACL root of trust in this foundation

#### Scenario: Document PVE identity bootstrap
- **WHEN** the PVE automation foundation is documented
- **THEN** documentation SHALL include a bootstrap runbook for creating `pve-ops@pve`, creating `pve-ops@pve!opentofu`, creating `pve-ops@pve!packer`, assigning initial role/ACLs, and filling the related 1Password API token items
- **AND** it SHALL state that future automation of this bootstrap may be introduced separately under an existing administrator identity

#### Scenario: Use generic host helper paths
- **WHEN** PVE helper source assets, bootstrap declarations, preflight or runtime callers select helper paths
- **THEN** the canonical names SHALL be `iaas-pve-template-build` and `iaas-pve-snippet-upload`, with matching sudoers and generic execution variables
- **AND** changing names SHALL preserve argument validation, dedicated identities, wrapper-only permissions and mutual exclusion
- **AND** existing hosts SHALL require an explicit documented cutover before new callers run, without silent old-name fallback or simultaneous old/new lock domains

### Requirement: 1Password runtime secret conventions
The system SHALL use environment-supplied 1Password references as the runtime source for infrastructure secrets, without a hard-coded vault in reusable execution paths. The existing Astra environment retains its current item conventions.

#### Scenario: Reference standardized 1Password items
- **WHEN** the Astra environment declares PVE or VM credentials
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
- **THEN** the runtime wrapper SHALL use `op run` with environment variables sourced from a committed template containing environment-selected `op://...` references (including `op://Astra/...` for the Astra environment)
- **AND** committed env templates SHALL NOT contain secret values

#### Scenario: Use a non-Astra vault without changing the runtime
- **WHEN** an environment supplies valid supported references to another vault
- **THEN** the runtime SHALL use those explicit references without substituting Astra defaults
- **AND** offline checks SHALL validate references without resolving them
- **AND** live CI secret access SHALL require a separately configured noninteractive identity, not a developer desktop login
