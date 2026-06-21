# OpenTofu PVE VM lifecycle

This directory is the root module for Section 4 of `add-pve-automation-foundation`.

## Inputs

- `generated.auto.tfvars.json` is loaded automatically.
- Runtime secrets are injected with `op run` using `.env.pve-opentofu.tpl`.
- No secrets are committed.
- `.env.pve-opentofu.tpl` sets `TF_VAR_pve_insecure=true` for the common PVE
  self-signed certificate case. Remove or override it if the cluster uses a
  trusted certificate chain.
- Runtime snippet cache files are written with parent directories `0700` and
  files `0600`.

## State

- Local state path: `terraform.tfstate`
- Backups: `.cache/tofu-state-backups/`
- Existing VMs are intentionally out of scope.
- `lifecycle_class` changes between the protected and unprotected module
  resources require state migration, not recreation:
  - unprotected -> protected:
    `tofu state mv 'module.ephemeral_vms["dev-web-01"].proxmox_virtual_environment_vm.unprotected[0]' 'module.long_lived_vms["dev-web-01"].proxmox_virtual_environment_vm.protected[0]'`
  - protected -> unprotected:
    `tofu state mv 'module.long_lived_vms["dev-web-01"].proxmox_virtual_environment_vm.protected[0]' 'module.ephemeral_vms["dev-web-01"].proxmox_virtual_environment_vm.unprotected[0]'`
  - If changing lifecycle class also changes VMID ranges, plan that separately;
    VMID changes are replacement-level changes.

## Usage

```bash
op run --env-file .env.pve-opentofu.tpl -- tofu init -backend=false
op run --env-file .env.pve-opentofu.tpl -- tofu validate
op run --env-file .env.pve-opentofu.tpl -- make plan STORAGE_ID=images
op run --env-file .env.pve-opentofu.tpl -- make apply STORAGE_ID=images PVE_HOST=cohe PVE_SSH_USER=pve-ops
```

`make plan` renders local cloud-init snippets only. `make apply` uploads and
verifies snippets before applying Terraform changes. `STORAGE_ID`, `PVE_HOST`,
and `PVE_SSH_USER` are intentionally explicit inputs; the Makefile does not
provide environment-specific defaults for them.

Cluster inventory drives the Ansible login user, cloud-init VM users, and the
snippet storage role/prefix used for rendered user-data files.

The provider uses `bpg/proxmox` `~> 0.109.0` with `ssh { agent = true username = "pve-ops" }` and token-based API auth.

## Safety notes

- Long-lived VMs are split into a separate module call with `prevent_destroy = true`.
- Ephemeral/lab VMs are intentionally not protected by default.
- Passthrough VMs are provisioned through `hostpci` resource mappings and remain in Section 5 scope; no raw PCI paths are accepted.
- Passthrough source YAML may optionally set `device_override` to pin a specific `hostpciN`; otherwise devices are auto-assigned per VM order.
- HA stays disabled for passthrough VMs, and this module does not move VMs between nodes or mutate host IOMMU/VFIO state.
- See `docs/runbooks/pve-pci-passthrough-readiness.md` for the host-side readiness checklist.
- Future TODO: manage PCI resource mappings with `bpg/proxmox` `proxmox_hardware_mapping_pci` from a separate high-privilege bootstrap root such as `infra/tofu/pve-mappings/`; keep this VM lifecycle root limited to consuming mapping names.
- `initialization[0].user_data_file_id` drift is ignored because the provider can otherwise churn externally managed cloud-init snippets; IP configuration and DNS remain Terraform-managed.
- OpenTofu manages VM lifecycle only. It does not create `pve-ops@pve`, its tokens, or the bootstrap ACLs.
- Both long-lived and ephemeral VMs are started after provisioning; only
  `on_boot` differs (`true` for long-lived, `false` for ephemeral).

## VM inventory fields and change risk

VMs may optionally declare:

- `resources.cores`, `resources.memory_mib`, `resources.root_disk_gib`
- `storage.disk_role`
- `boot.started`, `boot.on_boot`

Risk/behavior notes:

- changing `template` is replacement/high-risk
- changing `storage.disk_role` is replacement/high-risk
- decreasing `resources.root_disk_gib` is rejected by the generator because PVE cannot shrink disks
- increasing `resources.root_disk_gib` is an in-place resize
- changing `resources.cores` or `resources.memory_mib` is generally in-place
- changing `boot.started` or `boot.on_boot` is in-place
- cloud-init defaults affect newly initialized VMs only

## Section 4A cloud-init flow

Section 4A renders runtime cloud-init user-data snippets for each non-passthrough VM,
uploads them into isolated NFS-backed `images` snippets storage, and references them with
`user_data_file_id`.

- Snippet name: `opentofu-vm-<vmid>-user-data.yml`
- File ID: `images:snippets/opentofu-vm-<vmid>-user-data.yml`
- Retention: snippets stay in storage for the VM lifetime; do not delete them immediately after upload.

Use `op run --env-file .env.pve-opentofu.tpl -- make render-user-data STORAGE_ID=images` to create local snippets. `make plan` stays local. `make apply` runs `upload-user-data` and `verify-user-data` before the Terraform apply.

Required runtime env vars from `op run` (driven by the inventory-defined cloud-init users):

- `PVE_VM_CLEMON_PASSWORD`
- `PVE_VM_CLEMON_PUBLIC_KEY`
- `PVE_VM_OPS_PASSWORD`
- `PVE_VM_OPS_PUBLIC_KEY`

The runtime helper hashes passwords locally, writes only ignored cache files, and never logs plaintext secrets or password hashes.

Snippet upload and verify use the audited host-side wrapper `/usr/local/sbin/astra-pve-snippet-upload`; it does not rely on broad `sudo install` privileges. The wrapper installs files `0600` on non-NFS snippet storage and `0644` on NFS-backed storage to remain readable when root-squash or server-side ownership mapping is in effect. This is an intentional tradeoff for the isolated `images` NFS storage; do not use this mode on broadly shared or untrusted storage. Keep `STORAGE_ID` aligned with `local.snippets_datastore`.

## Live-test notes

- Section 4/4A was live-tested with VMID `500` (`dev-web-01`) on `cohe`, attached to `br_dev` with static IP `10.10.0.20/24`, then destroyed with a targeted OpenTofu destroy.
- PVE 9 required `AstraAutomation` on both the parent user `pve-ops@pve` and the privilege-separated token `pve-ops@pve!opentofu`.
- `AstraAutomation` also required `SDN.Use` for the `br_dev` SDN bridge check.
- Guest SSH for `ops` and `clemon` depends on the corresponding keys being available in the local SSH agent or 1Password SSH Agent.
- `astra-pve-template-build` is a bootstrap transitional wrapper for host-local template registration.

Example 1Password SSH Agent entries:

```toml
[[ssh-keys]]
item = "pve-ssh-automation-user"
vault = "Astra"

[[ssh-keys]]
item = "vm-user-ops"
vault = "Astra"

[[ssh-keys]]
item = "vm-user-clemon"
vault = "Astra"
```

## Manual backup helper

Use `make backup-state` before or after apply-like operations. `make apply` and `make destroy` call it automatically with `before`/`after` suffixes and a seconds-plus-PID timestamp to avoid collisions.

## Optional smoke checks

Manual validation against a live PVE node can be done later with:

```bash
ssh pve-ops@cohe 'sudo -n /usr/local/sbin/astra-pve-template-build --help'
ssh pve-ops@cohe 'sudo -n /usr/local/sbin/astra-pve-snippet-upload --help'
ssh <existing-admin-login>@cohe 'sudo -n visudo -cf /etc/sudoers.d/astra-pve-template-build'
ssh <existing-admin-login>@cohe 'sudo -n visudo -cf /etc/sudoers.d/astra-pve-snippet-upload'
```

Those checks are outside repository validation and are not required here.
