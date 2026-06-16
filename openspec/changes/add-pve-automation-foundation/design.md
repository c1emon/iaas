## Context

The target PVE environment is a cluster with shared storage and consistent per-node network configuration. Shared storage includes `images` for backups/imports/ISO images/snippets and `memory` for VM disk images. VM IP addressing should be static through cloud-init. The first template OS is Debian 13. VM count is expected to stay below 20, but the project should still use YAML inventory as a source of truth so OpenTofu inputs, Ansible inventory, and documentation do not diverge.

The current PVE network model is pre-existing Linux networking, not PVE SDN:

```text
mgmt    -> vmbr0   -> PVE management network
storage -> storage -> storage network
apps.10 -> br_dev  -> development VM network
apps.50 -> br_prod -> production VM network
```

All PVE nodes use the same bridge names and layout except for node-specific IP addresses. This change should reference those bridges for VM attachment but should not create or modify PVE host network interfaces.

The management and storage networks are PVE infrastructure networks only and are not VM attachment networks. Development and production VM networks are provided by OPNsense gateways and DNS at `10.10.0.254` and `10.50.0.254` respectively. This foundation does not create DNS or DHCP records in OPNsense for statically addressed VMs.

PCIe passthrough already uses a PVE PCI resource mapping named `iGpu0`, currently present on `cohe` and `node3`. OpenTofu should reference this resource mapping rather than hard-coding PCI addresses in VM definitions.

## Goals / Non-Goals

**Goals:**

- Build a Debian 13 PVE cloud-init template with Packer.
- Use YAML files as the source of truth for PVE cluster defaults, networks, templates, PCI mappings, and VM declarations.
- Generate OpenTofu variable input and Ansible inventory from the YAML source of truth.
- Use OpenTofu with the `bpg/proxmox` provider to create and manage new PVE VMs cloned from the Debian 13 template.
- Apply static IP, DNS, gateway, hostname, and SSH access through cloud-init/OpenTofu initialization.
- Attach VM NICs to existing bridges (`br_dev`, `br_prod`, and explicitly approved networks) without managing host network configuration.
- Support VM declarations that attach existing PCI resource mappings such as `iGpu0` through `hostpci` configuration.
- Keep OpenTofu state local initially with documented backup and single-operator assumptions.
- Reserve HA fields in inventory while keeping HA automation disabled.

**Non-Goals:**

- Do not manage PVE host network interface definitions, Linux bridges, VLAN subinterfaces, or gateways.
- Do not convert the cluster to PVE SDN in this change.
- Do not import, rename, destroy, or otherwise take over existing VMs.
- Do not enable PVE HA or automate HA groups/rules.
- Do not configure host BIOS, IOMMU, kernel command line, VFIO modules, or driver blacklists for passthrough.
- Do not manage OPNsense firewall/NAT/DHCP or switch VLAN/trunk/access configuration as part of VM provisioning.
- Do not introduce a remote OpenTofu backend in the first implementation.

## Decisions

### Use YAML inventory as source of truth

The system should keep operator-authored infrastructure facts in YAML files under a dedicated inventory area, for example:

```text
inventory/
├── pve-cluster.yml  # nodes, storage, networks, templates, PCI mappings, defaults
└── vms.yml          # VM declarations referencing symbols in pve-cluster.yml
```

The generator should produce OpenTofu input and Ansible inventory from these files. This keeps the VM list, IP addresses, node placement, Ansible groups, and lifecycle policy in one place.

The generator should be implemented in Python and run through the repository `uv` toolchain. It should emit committed non-sensitive generated files:

```text
infra/tofu/pve/generated.auto.tfvars.json
ansible/inventories/generated/pve.yml
docs/generated/pve-vms.md
```

Generated files must not contain passwords, password hashes, private keys, or token secrets. OpenTofu/Packer secret injection should use `op run` with a committed template env file containing 1Password references, not secret values.

Because the repository currently ignores `*.auto.tfvars.json`, the implementation must either add a precise `.gitignore` exception for `infra/tofu/pve/generated.auto.tfvars.json` or change the generated tfvars strategy before generator work is considered complete. If generated files are committed, a local validation target should detect stale generated output after source YAML changes.

Alternative considered: let OpenTofu read YAML directly with `yamldecode()`. Rejected for the first design because the project also needs generated Ansible inventory and preflight validation across PVE, network, and passthrough data.

### Build the template before VM provisioning

Packer should produce a Debian 13 cloud-init template before OpenTofu creates VMs. The source image should be Debian 13 `genericcloud`; the implementation must first run a spike to decide the most reliable import/build route and then pin the selected current image URL and checksum. The template should include cloud-init, enabled qemu-guest-agent, serial-console readiness, TUNA Debian apt mirrors, timezone `Asia/Shanghai`, locale `en_US.UTF-8`, baseline packages, and cleanup of unique machine state.

Packer should build on `cohe` by default and fail if that node is unavailable; operators can change the build node manually. Packer cache and downloaded image artifacts should live under `.cache/packer` and stay out of Git. Existing dated templates should be retained for rollback. If a requested template VMID/name already exists, replacement must require an explicit force mode that only allows VMIDs in `9000-9500` and names matching `debian-13-tmpl-*`.

Packer owns template creation. OpenTofu should reference templates by declared ID/name but should not manage the template VM lifecycle created by Packer.

Alternative considered: start with a manually created template. Rejected for the target design because the user explicitly wants Packer first and the repository is intended to make infrastructure reproducible.

### Keep cloud-init user data thin and generic

The Debian template should contain common packages and guest-agent readiness. VM-specific values such as hostname, static IP, gateway, DNS, and SSH keys should be provided through OpenTofu initialization rather than one unique user-data snippet per VM.

If future requirements need richer cloud-init content, snippets should use the shared `images` storage because it supports the `Snippets` content type and is visible cluster-wide.

Cloud-init should not run package update or upgrade on first boot; the template build and later Ansible baseline own package maintenance. SSH password authentication should be disabled. Hostname should use the short hostname plus a configurable global default domain/search domain that individual VMs may override.

### Separate human and automation VM users

Cloud-init should create separate Guest OS users for human administration and automation:

```text
clemon = human administration user
ops    = automation user for Ansible and other operational tooling
root   = not used for direct SSH login
```

Both `clemon` and `ops` should have sudo capability without passwordless sudo. Ansible should connect as `ops` and become root with sudo when privileged operations are required. Generated Ansible inventory should contain the non-secret connection model, but no passwords, private keys, tokens, or password hashes.

Root SSH login should be disabled by default. SSH access should use keys supplied at runtime through 1Password SSH Agent or the local SSH agent.

Alternative considered: connect Ansible directly as `root`. Rejected because separating `ops` from `root` gives a clearer audit boundary and avoids exposing direct root SSH as the default automation path.

### Use 1Password as runtime secret source

Secrets should come from the `Astra` 1Password vault. Item names should use short kebab-case, item grouping should use tags, and field names should use snake_case.

Initial items:

```text
pve-opentofu-api-token
pve-ssh-automation-user
vm-user-clemon
vm-user-ops
```

Recommended tags:

```text
pve-opentofu-api-token: pve, opentofu, api-token
pve-ssh-automation-user: pve, ssh, packer, opentofu
vm-user-clemon: vm, cloud-init, human-user
vm-user-ops: vm, cloud-init, ansible, automation-user
```

Recommended fields:

```text
username
password
public_key
private_key
token_id
token_secret
api_token
endpoint
```

1Password should store plaintext VM user passwords. The automation workflow should generate cloud-init-compatible password hashes at runtime, and generated repository files should not contain plaintext passwords, password hashes, private keys, or API token secrets.

Password hashes should be generated with Python `passlib` through the `uv` environment. `clemon` and `ops` should use independent passwords. The `ops` sudo password is the `ops` user password. The root account should not be a remote SSH entry point.

### Separate PVE API and SSH automation identities

The first implementation should use separate automation identities for PVE API access and node SSH access:

```text
PVE API user:  pve-ops@pve
PVE API token: pve-ops@pve!opentofu
PVE SSH user:  pve-ops
Packer token:  pve-ops@pve!packer
```

The `pve-ops@pve` user is a Proxmox VE realm identity whose API token and ACLs are stored in PVE cluster configuration. The `pve-ops` SSH user is a Linux node account used only for SSH operations required by Packer or the `bpg/proxmox` provider and should be provisioned consistently across nodes by a bootstrap process.

This separation avoids coupling API authorization to per-node PAM user state. The account pair should be dedicated to automation, use SSH key access for node login, use API tokens for PVE API access, and avoid reusing a personal user or `root@pam` identity.

The PVE API identity is a bootstrap prerequisite, not an OpenTofu-managed resource. Operators should create `pve-ops@pve`, create the `opentofu` token, assign its initial role/ACLs, and store the resulting token fields in 1Password before running OpenTofu. This avoids a self-management cycle where OpenTofu needs a token to create or repair the token it depends on.

The bootstrap process should be captured as a runbook with `pveum`/UI steps and the corresponding 1Password fields to fill. A later change may automate bootstrap with Ansible or a script that runs under an existing administrator identity, but VM lifecycle OpenTofu should not manage its own root credential path in this foundation.

OpenTofu and Packer should use separate API tokens stored in separate 1Password items:

```text
pve-opentofu-api-token -> pve-ops@pve!opentofu
pve-packer-api-token   -> pve-ops@pve!packer
```

The OpenTofu token should use the broad initial `PVEAutomation` role at `/` and privilege separation enabled (`privsep=1`), then be reduced later after observed required privileges are known. Packer should use a separate `PVETemplateBuilder` role, also refined after the Packer spike identifies actual requirements.

The Linux SSH user `pve-ops` should be provisioned on each PVE node by a bootstrap runbook plus Ansible playbook. Initial bootstrap login is provided at runtime by the operator. `pve-ops` should use SSH key authentication only, no password login, and limited `NOPASSWD` sudo. The sudo command allowlist must be based on the Packer/bpg spike rather than granting broad access by default.

### Treat PVE host networks as prerequisites

The current cluster network layout is consistent across nodes. VM declarations should reference logical networks such as `dev` and `prod`, which resolve to existing bridges `br_dev` and `br_prod`.

The generator should validate that VMs only attach to networks marked `attach_vms: true`. Management and storage networks should be rejected unless explicitly allowed.

The first implementation should support one primary NIC per VM. Network preflight should include static inventory checks plus read-only online checks that every target PVE node has required bridges such as `br_dev` and `br_prod`. Online checks should be separate from offline `make validate`, for example through a `make check-pve` target.

DNS record management is an explicit non-goal for this foundation. VM hostnames and FQDNs may not resolve after provisioning unless the operator creates DNS records through an existing manual process or a later OPNsense/DNS automation change.

Alternative considered: manage bridges and VLAN subinterfaces with OpenTofu or Ansible. Rejected for this change because host networking changes can disconnect the cluster and are outside the VM lifecycle foundation.

### Use PVE PCI resource mappings for passthrough

Passthrough VM declarations should reference resource mappings such as `iGpu0`, not raw PCI paths. The generator should validate that the selected VM node is listed under the mapping's allowed nodes.

Example model:

```yaml
pci_mappings:
  iGpu0:
    type: igpu
    nodes:
      cohe:
        path: "0000:00:02.1"
        iommu_group: 15
      node3:
        path: "0000:00:02.1"
        iommu_group: 13
    defaults:
      pcie: true
      rombar: true
      xvga: false
    ha_allowed: false
```

OpenTofu should render `hostpci` blocks using `mapping = "iGpu0"`. Passthrough VMs should require fixed node placement and HA disabled in this foundation.

The first passthrough schema should support the core fields `device`, `mapping`, `pcie`, `rombar`, and `xvga`. PCIe passthrough VMs must not be automatically migrated; node changes require an explicit human workflow.

PCIe passthrough should be treated as a second phase within this change. The first acceptance path is a non-passthrough ephemeral dev VM. Before implementing hostpci rendering, the project must verify the selected `bpg/proxmox` provider version supports PVE PCI resource mapping references as expected.

### Start with local OpenTofu state

State should start local and git-ignored. Documentation must state single-operator assumptions, backup expectations, and a future migration path to a remote backend if collaboration increases.

The initial local state path should be `infra/tofu/pve/terraform.tfstate`. The state file is not encrypted for the first implementation and should not be committed.

State backup should not rely only on operator memory. Makefile/OpenTofu helper targets should automatically copy local state to a timestamped path under `.cache/tofu-state-backups/` before and/or after apply-like operations. A remote backend is deferred.

### Use fixed VM ID ranges and template naming

The Debian 13 genericcloud image source should be selected as the current latest image at implementation time and then pinned. Template names should use the form `debian-13-tmpl-{date}`, with a compact date such as `debian-13-tmpl-20260616` unless implementation reveals a PVE naming constraint.

VM ID ranges should be reserved as follows:

```text
9000-9500 = templates
1000-2000 = long-lived VMs
500-800   = ephemeral/lab VMs
```

Packer should build templates on `cohe` by default. Long-lived VMs should default to boot on host startup. Ephemeral/lab VMs may be destroyable and should not boot on host startup by default.

VM IDs are manually declared in YAML and validated against the reserved ranges. Templates also use manually declared VMIDs. Default VM sizing is `2` cores, `2048` MiB memory, and `20` GiB root disk, with VM-level overrides allowed. VM disks default to datastore `memory`, `virtio-scsi-single`, and `scsi0`; root disk size should follow inventory. VM clones should be full clones. CPU type defaults to `host`, BIOS/machine defaults to `OVMF` + `q35`, and qemu-guest-agent should be enabled in both the template and VM configuration.

PVE VM tags should combine automatically generated tags such as `managed-by-opentofu`, lifecycle, network, and role with operator-provided inventory tags. PVE pool assignment is optional per VM. PVE VM-level firewall is out of scope.

OVMF requires EFI disk handling. The implementation must verify that the chosen storage and `bpg/proxmox` configuration support EFI disks on the intended datastore before the first template/VM acceptance is complete.

Existing VMs are documentation-only in this foundation and must not be imported or modified.

Makefile should be the local command entry point, with targets for generation, validation, Packer build, OpenTofu plan/apply helpers, and Ansible checks. Tool versions should be documented and constrained through provider/plugin constraint files; exact CLI pinning through mise/asdf is deferred.

The first disposable acceptance VM should be an ephemeral dev VM on `cohe`, attached to `br_dev`, with a VMID in `500-800`, no PCIe passthrough, and full basic validation including Packer template, OpenTofu plan/apply, static IP, SSH as `clemon` and `ops`, `ops` sudo, qemu-guest-agent, generated Ansible inventory/ping, and destroy of the ephemeral VM.

## Risks / Trade-offs

- Packer Proxmox template builds can be sensitive to ISO/cloud-image boot behavior → keep template build tasks isolated and document rebuild steps.
- Packer genericcloud import and `pve-ops` sudo allowlist are unknown → add a spike before implementation to select the build route and least-broad sudo command set.
- Committed generated tfvars conflict with current `.gitignore` patterns → resolve the ignore/exception strategy before relying on generated output review.
- Local OpenTofu state can be lost or diverge → require state backup guidance and avoid multi-operator workflows until a remote backend is introduced.
- DNS records are not managed → document that static-IP VMs may need manual DNS registration until a later DNS automation change.
- PVE automation identity bootstrap is manual at first → document exact user, token, role, ACL, and 1Password steps so the root of trust is reproducible without making OpenTofu manage its own credentials.
- `prevent_destroy` and lifecycle policy are essential for long-lived VMs → generated input or module design must protect long-lived VMs by default.
- PVE host networks are manually maintained → add preflight/read-only checks before applying VMs, but do not mutate host network configuration.
- PCIe passthrough binds VMs to physical node capabilities → validate node/mapping compatibility and keep HA disabled.
- Debian 13 cloud images/templates may need guest-specific tuning for qemu-guest-agent and serial console behavior → verify with a disposable VM before declaring the template usable.

## Migration Plan

1. Define YAML source-of-truth schemas for PVE defaults, networks, templates, PCI mappings, and VM declarations.
2. Run spike research for Debian genericcloud-to-PVE-template build route and `pve-ops` limited sudo allowlist.
3. Add a generator plan that validates YAML and emits OpenTofu `generated.auto.tfvars.json`, Ansible `pve.yml`, and generated docs.
4. Document the manual PVE API identity bootstrap for `pve-ops@pve`, the `opentofu` and `packer` tokens, role/ACL assignment, and 1Password population.
5. Add PVE node bootstrap runbook/playbook for `pve-ops` SSH user, authorized key, and limited sudoers.
6. Add Packer design/runbook for the Debian 13 PVE template on shared storage.
7. Add OpenTofu PVE design using the `bpg/proxmox` provider and local state.
8. Add ordinary VM creation flow using the Debian 13 template, static cloud-init IP, and `br_dev`/`br_prod` network attachments.
9. Add PCI resource mapping support for VMs that declare passthrough, starting with `iGpu0`.
10. Add Ansible inventory generation and a baseline verification plan for new VMs.
11. Validate the full path on disposable dev/lab VMs before any long-lived production VM is declared.

## Open Questions

- What exact least-privilege PVE role should be assigned to `pve-ops@pve!opentofu` after provider behavior is validated?
- What exact least-privilege PVE role should be assigned to `pve-ops@pve!packer` after Packer spike validation?
- What exact limited `NOPASSWD` sudo allowlist should `pve-ops` receive after spike validation?
- What default VM domain/search domain should be configured?
- What is the preferred future remote backend if local state becomes insufficient?
