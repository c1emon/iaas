## 0. Spike / Preflight Research

- [x] 0.1 Research and choose the Debian 13 genericcloud-to-PVE-template implementation route before coding Packer.
- [x] 0.2 Research the `bpg/proxmox` and Packer SSH command requirements for `pve-ops` and define a limited `NOPASSWD` sudo allowlist.
- [x] 0.3 Confirm first-version Packer plugin and `bpg/proxmox` provider minor-version constraints.
- [x] 0.4 Verify the selected `bpg/proxmox` provider supports PVE PCI resource mapping references for `hostpci` as expected.
- [x] 0.5 Verify OVMF/EFI disk support on the chosen storage and provider configuration.
- [x] 0.6 Resolve the `.gitignore` conflict for committed `infra/tofu/pve/generated.auto.tfvars.json` or change the generated tfvars strategy.

## 1. Source-of-Truth Model

- [x] 1.1 Define `inventory/pve-cluster.yml` schema for cluster nodes, storage roles, defaults, network assumptions, templates, and PCI resource mappings.
- [x] 1.2 Define `inventory/vms.yml` schema for VM resources, lifecycle class, node placement, network, static IP, Ansible groups, HA placeholders, optional pool, tags, and optional passthrough.
- [x] 1.3 Add schema validation before generation so invalid YAML can be rejected without producing outputs.
- [x] 1.6 Encode reserved VM ID ranges: `9000-9500` for templates, `1000-2000` for long-lived VMs, and `500-800` for ephemeral/lab VMs.
- [x] 1.7 Encode default storage roles: `memory` for VM/template disks and `images` for ISO/import/snippets.
- [x] 1.8 Encode dev/prod networks: `br_dev` with `10.10.0.0/24` gateway/DNS `10.10.0.254`, and `br_prod` with `10.50.0.0/24` gateway/DNS `10.50.0.254`.
- [x] 1.9 Record PVE node `mgmt_ip`, `storage_ip`, and optional `ssh_host` while marking management/storage networks as not attachable for VMs.
- [x] 1.10 Encode global VM defaults: `2` cores, `2048` MiB memory, `20` GiB root disk, `host` CPU, `OVMF`, `q35`, full clone, `virtio-scsi-single`, `scsi0`, one primary NIC, and optional pool.

## 2. Generator and Validation Design

- [x] 2.1 Add a generator that reads source YAML and emits OpenTofu `generated.auto.tfvars.json`.
- [x] 2.2 Add Ansible inventory generation from the same VM source data.
- [x] 2.2a Add generated documentation output such as `docs/generated/pve-vms.md`.
- [x] 2.3 Validate unique VM IDs, hostnames, IP addresses, and VM names.
- [x] 2.4 Validate VM IPs against their declared network CIDRs and reject VM attachment to networks that are not `attach_vms: true`.
- [x] 2.5 Validate node, template, network, storage, lifecycle, and HA placeholder values.
- [x] 2.6 Validate PCI passthrough declarations by requiring the VM node to be present in the selected PCI mapping.
- [x] 2.7 Reject HA-enabled VMs and passthrough HA combinations until HA automation is explicitly implemented.
- [x] 2.8 Validate VM IDs against their lifecycle/template ranges.
- [x] 2.9 Ensure generated files contain no passwords, password hashes, private keys, or token secrets.
- [x] 2.10 Implement the generator in Python using `uv` and `passlib` for cloud-init password hash generation.
- [x] 2.11 Emit committed non-sensitive outputs at `infra/tofu/pve/generated.auto.tfvars.json`, `ansible/inventories/generated/pve.yml`, and `docs/generated/pve-vms.md`.
- [x] 2.12 Add validation that generated files are up to date with source YAML.

## 3. Packer Debian 13 Template Foundation

- [x] 3.1 Decide whether the first Debian 13 template build uses installer ISO automation or Debian genericcloud image import.
- [x] 3.2 Define Packer variables for PVE endpoint, node, ISO/import storage `images`, VM disk storage `memory`, VM ID, template name, and credentials.
- [x] 3.3 Install and enable cloud-init and qemu-guest-agent in the template.
- [x] 3.4 Configure serial-console-compatible display behavior for cloud images.
- [x] 3.5 Clean machine identity, SSH host keys, cloud-init state, package cache, and temporary files before templating.
- [x] 3.6 Document template rebuild and versioning runbook.
- [x] 3.7 Pin the selected current Debian 13 genericcloud image URL and checksum at implementation time.
- [x] 3.8 Use `cohe` as the default Packer build node and `debian-13-tmpl-{date}` as the template naming convention.
- [x] 3.9 Configure TUNA Debian apt mirrors, timezone `Asia/Shanghai`, and locale `en_US.UTF-8` in the template.
- [x] 3.10 Store Packer cache/download artifacts under `.cache/packer` and keep them out of Git.
- [x] 3.11 Retain old dated templates by default and require explicit force for replacement.
- [x] 3.12 Restrict template force replacement to VMIDs `9000-9500` and names matching `debian-13-tmpl-*`.
- [x] 3.13 Keep Packer-created templates owned by Packer; OpenTofu may reference but not manage template lifecycle.
- [x] 3.14 Execute an end-to-end Debian 13 template build on cohe and validate the resulting template.

## 4. OpenTofu PVE VM Lifecycle

- [x] 4.1 Add OpenTofu provider design using `bpg/proxmox` with API token and SSH configuration.
- [x] 4.2 Use local, git-ignored OpenTofu state with documented backup guidance.
- [x] 4.3 Define a VM module or equivalent resource structure for cloning from the Debian 13 template.
- [x] 4.4 Configure CPU, memory, disk on `memory`, network device bridge selection, tags, and VM startup state from generated input.
- [x] 4.5 Configure static cloud-init initialization for hostname, IP address, gateway, DNS, and SSH access.
- [x] 4.6 Protect long-lived VMs from accidental destroy by default.
- [x] 4.7 Keep existing VMs out of scope; do not import production VM state in this change.
- [x] 4.8 Store local OpenTofu state at `infra/tofu/pve/terraform.tfstate` and keep it out of Git.
- [x] 4.9 Use separate dedicated automation identities: API user `pve-ops@pve`, API token `pve-ops@pve!opentofu`, and SSH user `pve-ops` provisioned on PVE nodes.
- [x] 4.10 Document that `pve-ops@pve`, its `opentofu` token, and initial role/ACL assignments are manually bootstrapped before OpenTofu runs.
- [x] 4.11 Ensure OpenTofu does not manage the PVE API user, the token it uses, or its own initial ACLs in this foundation.
- [x] 4.12 Use the `AstraAutomation` role at `/` with token privilege separation enabled for the initial OpenTofu token, then document follow-up least-privilege reduction.
- [x] 4.13 Add a `pve-packer-api-token` 1Password item and use `pve-ops@pve!packer` with a separate `AstraTemplateBuilder` role for Packer.
- [x] 4.14 Use `op run` and a committed env template with `op://Astra/...` references for runtime secret injection.
- [x] 4.15 Add OpenTofu module structure under `infra/tofu/modules/pve-cloudinit-vm` and consume it from `infra/tofu/pve`.
- [x] 4.16 Add Makefile/OpenTofu helper behavior that backs up local state to `.cache/tofu-state-backups/` before and/or after apply-like operations.
- [x] 4.17 Live-test disposable VM create/start/guest-agent/SSH/destroy on `cohe` with VMID `500` attached to `br_dev`.

## 4B. PVE Identity Bootstrap Runbook

- [x] 4B.1 Add a runbook for creating the PVE realm user `pve-ops@pve`.
- [x] 4B.2 Add a runbook step for creating the API token `pve-ops@pve!opentofu`.
- [x] 4B.3 Add a runbook step for creating the API token `pve-ops@pve!packer`.
- [x] 4B.4 Add a runbook step for assigning the initial `AstraAutomation` and `AstraTemplateBuilder` roles/ACLs.
- [x] 4B.5 Add a runbook step for storing `username`, `token_id`, `token_secret`, `api_token`, and `endpoint` in `Astra/pve-opentofu-api-token` and `Astra/pve-packer-api-token`.
- [x] 4B.6 Add a note that a future change may automate bootstrap with Ansible or scripts, but not with the OpenTofu configuration that consumes the token.

## 4C. PVE Node SSH Bootstrap

- [x] 4C.1 Add a PVE node bootstrap playbook/runbook that creates `pve-ops` on each PVE node using a runtime-specified existing administrator login.
- [x] 4C.2 Configure `pve-ops` for SSH key authentication only, with no password login.
- [x] 4C.3 Install the `pve-ssh-automation-user` public key for `pve-ops` on each node.
- [x] 4C.4 Configure limited `NOPASSWD` sudoers for `pve-ops` based on spike results, not `NOPASSWD: ALL`.
- [x] 4C.5 Deploy `infra/pve-node/bin/astra-pve-template-build` to `/usr/local/sbin/astra-pve-template-build` as `root:root` with mode `0750`.
- [x] 4C.6 Add non-mutating post-bootstrap checks for wrapper presence and sudoers validation, with wrapper-only sudo as the default and a temporary override for preflight.
- [x] 4C.7 Document that this extension does not manage global PVE node SSHD policy.

## 4A. Guest User and Secret Model

- [x] 4A.1 Configure cloud-init to create `clemon` as the human administration user.
- [x] 4A.2 Configure cloud-init to create `ops` as the automation user.
- [x] 4A.3 Grant `clemon` and `ops` sudo capability without passwordless sudo.
- [x] 4A.4 Disable direct root SSH login by default.
- [x] 4A.5 Retrieve VM user passwords and SSH public keys from the `Astra` 1Password vault at runtime.
- [x] 4A.6 Generate cloud-init password hashes at runtime from plaintext passwords stored in 1Password.
- [x] 4A.7 Use 1Password SSH Agent or the local SSH agent for SSH private key access.
- [x] 4A.8 Document 1Password item naming, tags, and snake_case fields for `pve-opentofu-api-token`, `pve-ssh-automation-user`, `vm-user-clemon`, and `vm-user-ops`.
- [x] 4A.9 Live-test cloud-init creation of `clemon` and `ops` with sudo group membership and key-based SSH access.

## 5. PCIe Passthrough VM Support

- [ ] 5.1 Render `hostpci` blocks from VM passthrough declarations using PVE resource mapping names, not raw PCI addresses.
- [ ] 5.2 Support the existing `iGpu0` mapping on `cohe` and `node3`.
- [ ] 5.3 Require passthrough VMs to use compatible defaults such as `q35`, `ovmf`, and `cpu: host` unless explicitly overridden safely.
- [ ] 5.4 Keep HA disabled for passthrough VMs and document migration limitations.
- [ ] 5.5 Add a runbook or checklist for host-side PCI passthrough readiness without automatically changing IOMMU/VFIO host configuration.
- [ ] 5.6 Support first-version passthrough fields `device`, `mapping`, `pcie`, `rombar`, and `xvga`.
- [ ] 5.7 Reject automatic node changes/migration for passthrough VMs.
- [ ] 5.8 Treat PCIe passthrough as phase B; do not block first disposable VM acceptance on passthrough support.

## 6. Ansible Integration and Verification

- [ ] 6.1 Generate Ansible inventory groups from VM `ansible_groups` declarations.
- [ ] 6.2 Add a verification workflow plan for SSH reachability, hostname, static IP, DNS, and qemu-guest-agent readiness.
- [ ] 6.3 Keep guest OS service configuration in Ansible roles rather than Packer or OpenTofu.
- [ ] 6.4 Document the boundary between OpenTofu-owned VM lifecycle and Ansible-owned guest configuration.
- [ ] 6.5 Generate Ansible inventory with `ansible_user: ops`, sudo become settings, and no embedded secrets.
- [ ] 6.6 Disable VM SSH password authentication and root SSH login by default.
- [ ] 6.7 Do not run cloud-init package update/upgrade on first boot.

## 7. Documentation and Validation

- [ ] 7.1 Add decision notes for OpenTofu over Terraform, `bpg/proxmox`, YAML source-of-truth, local state, and bridge-based networking.
- [ ] 7.2 Document storage roles: `images` for ISO/import/snippets and `memory` for VM/template disks.
- [ ] 7.3 Document that PVE host network configuration is a prerequisite and is not mutated by this change.
- [ ] 7.4 Validate source YAML, generated OpenTofu variables, and generated Ansible inventory with repository linting tools where practical.
- [ ] 7.5 Run Packer validation, OpenTofu format/validate/plan, and Ansible inventory validation for a disposable VM before marking the change complete.
- [ ] 7.6 Document `br_dev` as `10.10.0.0/24` with gateway/DNS `10.10.0.254` and `br_prod` as `10.50.0.0/24` with gateway/DNS `10.50.0.254`.
- [ ] 7.7 Document the bootstrap/IaC boundary: PVE API identity and root of trust are bootstrap-managed; VM lifecycle is OpenTofu-managed.
- [ ] 7.8 Add Makefile targets for generation, offline validation, online PVE checks, Packer build, OpenTofu plan/apply helpers, and Ansible checks.
- [ ] 7.9 Update top-level README from `terraform/` planning to `infra/tofu/` and `infra/packer/`.
- [ ] 7.10 Document local state manual backup runbook and defer remote backend.
- [ ] 7.11 Validate a first disposable dev VM on `cohe` attached to `br_dev`, without PCIe passthrough, including create/configure/Ansible/destroy acceptance.
- [ ] 7.12 Document DNS as a non-goal: static-IP VM hostname/FQDN resolution is not guaranteed until DNS records are handled manually or by a later change.
