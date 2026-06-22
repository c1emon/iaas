# IaaS automation roadmap research

This note captures the June 2026 exploration of comparable homelab/IaaS automation projects and the resulting direction for this repository. Use it as input for future OpenSpec proposals rather than as an implementation plan by itself.

## Current repository position

This repository is a small-scale Astra IaaS automation workspace centered on Proxmox VE, OpenTofu, Packer, Ansible, OPNsense, and switch/network operations.

Current design boundaries:

- `inventory/pve-cluster.yml` and `inventory/vms.yml` are the operator-authored source of truth for PVE cluster facts and VM declarations.
- `scripts/pve_inventory/` validates and normalizes inventory, then generates OpenTofu variables, Ansible inventory, generated VM documentation, and Packer template build environment data.
- Packer owns reusable PVE templates.
- OpenTofu owns new VM lifecycle.
- Ansible owns guest OS and network/service configuration.
- PVE host networking, IOMMU/VFIO, PCI resource mapping creation, and bootstrap root-of-trust are prerequisites or separate bootstrap concerns, not routine VM apply behavior.

Recent section 5 PCIe passthrough work added:

- PVE resource mapping based passthrough via `hostpci { mapping = "..." }`.
- No raw PCI path in VM declarations.
- `scripts/pve_inventory/passthrough.py` for passthrough validation and normalization.
- Automatic per-VM `hostpci0..hostpci15` allocation.
- Optional `device_override` for explicit slot pinning.
- Validation for mapping existence, node compatibility, HA-disabled passthrough, mapping default flags, duplicate `(node, mapping)` use, duplicate override values, hostpci exhaustion, and clear missing-field errors.
- Readiness runbook documenting host-side prerequisites and future mapping bootstrap direction.

## Comparable project categories

### Full-stack closed-loop homelab platforms

Examples:

- `khuedoan/homelab`
- `sfcal/homelab`
- `Mafyuh/iac`
- `Starktastic-Homelab/terraform` and related repos

Typical pattern:

```text
bare metal / Packer / templates
  -> Terraform/OpenTofu provisioning
  -> Ansible host or cluster configuration
  -> Kubernetes / Flux / ArgoCD app layer
  -> monitoring, backup, DNS, certificates, remote access
```

Useful ideas:

- Clear staged pipeline: bootstrap, generate, validate, provision, configure, verify.
- CI validation and plan review.
- Service metadata as a single source of truth for DNS/reverse proxy/app exposure.
- Packer manifest or template version guard between image build and VM provisioning.

Not appropriate now:

- Full GitOps app platform as the main repository goal.
- Automatic production apply from CI.
- Large Kubernetes platform scope before the PVE/IaaS foundation is stable.

### Network source-of-truth systems

Examples:

- `netbox-community/netbox-zero-to-hero`
- `netbox.netbox.nb_inventory`
- NetBox Ansible collection and inventory plugins

Core idea:

```text
NetBox = DCIM/IPAM source of truth
automation reads device, interface, VLAN, prefix, IP, VM, and site facts from NetBox
```

Useful ideas:

- Model physical devices, interfaces, VLANs, prefixes, IP addresses, and VM records explicitly.
- Use one source of truth for switch, firewall, VM inventory, and documentation data.
- Dynamic inventory can verify or replace hand-maintained inventory when scale justifies it.

Current recommendation:

- Do not introduce NetBox yet.
- Keep YAML source of truth, but shape YAML concepts toward NetBox-like entities where useful.
- Reconsider NetBox only if VLAN/IP/device scale, IP conflicts, or multi-operator workflow require it.

### Proxmox VE host and cluster automation

Examples:

- `lae/ansible-role-proxmox`
- `enix/ansible-proxmox-ve`
- `Vezpi/Homelab` update playbook and article

Useful ideas:

- PVE repository, no-subscription source, datacenter config, RBAC, roles, users, ACLs.
- Storage configuration for NFS, iSCSI, PBS, LVM, ZFS, CephFS, RBD.
- Cluster health preflight: quorum, storage, Ceph health when applicable.
- Rolling PVE maintenance: node maintenance mode, migrate guests, Ceph `noout`, reboot, post-check, notification.
- Semaphore UI and Ntfy as lightweight scheduled playbook and notification tools.

Current recommendation:

- Keep PVE host/bootstrap operations separate from VM lifecycle.
- Add read-only online preflight before mutation.
- Consider PVE update/maintenance playbooks only after runbooks and checks are stable.

### Proxmox VM lifecycle with Terraform/OpenTofu

Examples:

- `bpg/terraform-provider-proxmox`
- `RemiGascou/terraform-proxmox-kubernetes-cluster`
- `vinetos/infrastructure`

Useful ideas:

- Continue using `bpg/proxmox` as the primary PVE provider.
- Use provider resources where they reduce custom shell code.
- Future PCI mapping bootstrap can use `proxmox_hardware_mapping_pci` in a separate high-privilege root.
- Terraform/OpenTofu can generate Ansible inventory, but this repository's Python generator is a better fit because it also generates docs and Packer environment data.

Current recommendation:

- Keep the current YAML -> Python -> generated tfvars/inventory/docs/env flow.
- Avoid importing PVE host network configuration into state for now; prefer read-only checks.
- Keep VM root limited to consuming cluster mappings and creating/updating VMs.

### Domestic / localized operations references

Examples:

- `Geek-Research-Lab/HomeLab-Guide`
- `stilleshan/server`

Useful ideas:

- Chinese-language runbooks.
- IPv6 DDNS and cloud DNS provider notes.
- apt, Docker, GitHub, container registry mirror guidance.
- Firewall hardening and multi-host backup practices.

Current recommendation:

- Add optional runbooks for domestic network acceleration and DNS/DDNS only if needed by operators.
- Do not bake locale-specific assumptions into core generators.

## Tooling worth considering

### Adopt or deepen soon

- `bpg/proxmox`: already in use; continue using for VM lifecycle and future PCI hardware mapping bootstrap.
- `community.proxmox`: use for read-only online checks, dynamic inventory comparison, storage/VM facts, and possibly storage bootstrap later.
- `oxlorg.opnsense` / `ansibleguy.opnsense`: continue using Ansible collections for OPNsense instead of custom API clients.
- `gitleaks` or `trufflehog`: secret scanning for generated files, env templates, tfvars mistakes, and cloud-init artifacts.
- `yamllint`: YAML is source-of-truth and should be linted.
- `pre-commit`: unify local hygiene checks.

### Useful later

- `ansible-lint`: enable incrementally, especially for new playbooks.
- `ntfy`: lightweight notifications for maintenance, long-running jobs, and failures.
- `community.proxmox.proxmox_storage`: possible storage check/bootstrap path.
- `lae.proxmox`: reference or direct role for deeper PVE host bootstrap, if the repository grows in that direction.

### Defer until scale demands it

- NetBox and `netbox.netbox` collection.
- Terragrunt.
- Remote state backend.
- SOPS/age or Sealed Secrets for non-Kubernetes IaaS secrets.
- Semaphore UI.
- GitOps auto-apply for PVE or network changes.

## Council guidance summary

Council consensus was high:

- The repository's current design is healthy for small-scale IaaS automation.
- The main risk is platform creep.
- The next work should improve reliability, validation, and operational closure rather than expand scope.
- NetBox, Terragrunt, and GitOps should be trigger-based future options, not near-term defaults.

Hard rules to preserve the current positioning:

1. Default checks should be offline and safe.
2. Online operations must be explicit.
3. Routine VM apply must not mutate PVE host networking, IOMMU/VFIO, cluster bootstrap, or high-privilege hardware mapping state.
4. High-privilege bootstrap roots must be separate from routine VM lifecycle roots.
5. CI should validate and report; it should not auto-apply PVE, firewall, or switch changes.
6. New tools must solve a current pain point.
7. YAML is sufficient until scale forces a stronger source-of-truth system.
8. Generate docs/plans before introducing mutation.

## Recommended roadmap

### P0: 1-2 week reliability work

Goal: make existing capabilities repeatable and easy to validate.

Candidate OpenSpec changes:

- Add root `Makefile` or `Taskfile` targets:
  - `generate`
  - `check-generated`
  - `test`
  - `lint-yaml`
  - `tofu-fmt`
  - `tofu-validate`
  - `pve-plan`
  - `pve-preflight`
  - `ansible-pve-ping`
  - `check`
- Add CI validation only:
  - pytest
  - generator `--check`
  - OpenTofu fmt/validate
  - yamllint
  - staged ansible-lint or syntax-check
  - gitleaks/trufflehog
- Add state and secret runbooks:
  - local state backup/restore
  - `.cache` handling
  - 1Password env injection conventions
  - generated output non-secret expectations
- Reconfirm passthrough edge cases:
  - passthrough VM without cloud-init user-data and Ansible inventory behavior
  - `null`/`[]` handling in OpenTofu locals and dynamic blocks

### P1: 1-2 month operational closure

Goal: move from VM creation to safe operation of a small PVE environment.

Candidate OpenSpec changes:

- Add read-only PVE online preflight:
  - API token works
  - nodes exist
  - bridges exist
  - storage exists and content types match expectations
  - template VMID/name exists and is a template
  - VMIDs are free or already owned as expected
  - PCI mappings exist and `check-node` passes
  - snippet storage and wrappers are present
- Add generated/Ansible guest verification:
  - SSH reachable
  - hostname/static IP/DNS
  - qemu-guest-agent
  - `ops` sudo/become
  - root SSH disabled
  - expected groups/tags
- Add lightweight notification helper:
  - Ntfy or equivalent for long-running/maintenance workflows.
- Add optional `inventory/services.yml` as service metadata source:
  - initially generate docs only
  - fields: service name, owner VM, FQDN, port, protocol, exposure, auth, DNS/reverse proxy/OPNsense hints
- Add PVE operations runbooks/playbooks:
  - cluster health check
  - rolling reboot/update design
  - Ceph handling only if Ceph is introduced

### P2: long-term scale-triggered work

Only pursue these when the repository outgrows the simpler model:

- `infra/tofu/pve-mappings/` for `proxmox_hardware_mapping_pci` with high-privilege credentials.
- Remote OpenTofu state when multi-operator or CI apply becomes real.
- NetBox when IP/VLAN/device facts outgrow YAML.
- Terragrunt when OpenTofu roots/environments multiply and backend/provider duplication becomes painful.
- GitOps for Kubernetes/application layer, not PVE host or VM lifecycle.
- OPNsense/DNS/switch mutation after read-only export/diff and generated plan documentation exist.

## Future OpenSpec proposal seeds

Use these as possible change names and scopes:

1. `add-iaas-validation-entrypoints`
   - Root Makefile/Taskfile, offline `make check`, generator check, tests, OpenTofu validation.

2. `add-pve-online-preflight`
   - Read-only PVE checks for API, nodes, storage, bridges, templates, PCI mappings, snippets.

3. `document-pve-state-and-secret-operations`
   - State backup/restore, secret injection, cache hygiene.

4. `add-pve-guest-verification`
   - Ansible verification workflow from generated inventory.

5. `add-service-metadata-inventory`
   - Lightweight `inventory/services.yml`, generated docs only at first.

6. `add-pve-operations-runbooks`
   - PVE health, maintenance, rolling reboot/update pattern, optional Ntfy notification.

7. `add-pve-hardware-mapping-bootstrap`
   - Future separate OpenTofu root for `proxmox_hardware_mapping_pci`; high-privilege and low-frequency only.

## Design cautions

- Do not convert this repository into a general-purpose platform unless the operating model requires it.
- Prefer explicit, reviewed commands over fully automatic mutation.
- Avoid coupling unrelated layers: VM apply should not change firewall, switch, PVE host network, or cluster hardware mappings.
- Prefer small OpenSpec changes that add one safety rail or one operational workflow at a time.
- Keep generated committed artifacts reviewable and non-sensitive.
