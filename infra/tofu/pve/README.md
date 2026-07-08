# OpenTofu PVE VM lifecycle

This directory is the root module for the PVE VM lifecycle foundation in
`add-pve-automation-foundation`.

OpenTofu owns VM lifecycle, cloud-init identity, and VM NIC attachment.
Packer owns the reusable template. Ansible owns guest OS service configuration
and read-only verification. YAML inventory is the source of truth.

## Inputs

- `generated.auto.tfvars.json` is loaded automatically.
- Runtime secrets are injected with `op run` using `.env.pve-opentofu.tpl`.
- No secrets are committed.
- `.env.pve-opentofu.tpl` sets `TF_VAR_pve_insecure=true` for the common PVE
  self-signed certificate case. Remove or override it if the cluster uses a
  trusted certificate chain.
- Runtime snippet cache files are written with parent directories `0700` and
  files `0600`.

## Storage and network assumptions

- `images` is the shared NFS content store for ISO/import/snippets.
- `memory` is the shared VM/template disk store for root, EFI, and cloud-init
  drive media.
- `br_dev` maps to `10.10.0.0/24` with gateway/DNS `10.10.0.254`.
- `br_prod` maps to `10.50.0.0/24` with gateway/DNS `10.50.0.254`.
- PVE host bridge configuration is a prerequisite and is not mutated here.

## VM network inventory

VM declarations use the explicit `nics` model. Zero-NIC VMs are valid and VMs
with NICs render dynamic network devices plus cloud-init network-config:

```yaml
- name: dev-web-01
  vmid: 500
  lifecycle_class: ephemeral_lab
  node: cohe
  network: dev
  static_ip: 10.10.0.20/24
  gateway: 10.10.0.254
  dns: [10.10.0.254]
```

Explicit multi-NIC declarations use reviewed deterministic MAC addresses and
stable guest interface names. Cloud-init network-config matches by MAC address
and applies `set-name`, avoiding fragile guest NIC ordering:

```yaml
- name: k3s-cp-01
  vmid: 1101
  lifecycle_class: long_lived
  node: cohe
  nics:
    - name: mgmt0
      role: management
      network: prod
      macaddr: bc:24:11:00:11:01
      static_ip: 10.50.0.31/24
      gateway: 10.50.0.254
      dns: [10.50.0.254]
    - name: cluster0
      role: cluster
      network: k3s-cluster
      macaddr: bc:24:11:00:21:01
      static_ip: 10.20.0.31/24
    - name: storage0
      role: storage
      network: k3s-storage
      macaddr: bc:24:11:00:31:01
      static_ip: 10.30.0.31/24
    - name: ingress0
      role: ingress
      network: k3s-ingress
      macaddr: bc:24:11:00:41:01
      static_ip: 10.40.0.31/24
```

K3s-target VM role convention:

- `mgmt0` / `management` — recommended future K3s management interface and the
  usual Ansible connection NIC, but not required by the generic base model.
- `cluster0` / `cluster` — Cilium/K3s node-to-node underlay traffic.
- `storage0` / `storage` — storage replication or data-plane traffic when an
  attachable storage-like VM network is explicitly introduced.
- `ingress0` / `ingress` — service or load-balancer ingress traffic.

Every explicit NIC needs a unique MAC address. Plan MACs in inventory first,
review generated artifacts, then render cloud-init snippets. Do not rely on
Proxmox-generated MACs or guest names such as `ens18` for multi-NIC guests.

## State

- Local state path: `infra/tofu/pve/terraform.tfstate`
- Backups: `.cache/tofu-state-backups/`
- Use `make backup-state` before and/or after apply-like operations.
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

Repository root offline validation uses `make check`. That root flow now also
checks the committed service metadata docs. This module keeps the more explicit
module-local commands for validation, planning, and mutation.

### Offline validation from the repo root

```bash
make generate
make check-generated
make check
```

### Module-local validation and mutation

```bash
op run --env-file .env.pve-opentofu.tpl -- tofu init -backend=false
op run --env-file .env.pve-opentofu.tpl -- tofu validate
op run --env-file .env.pve-opentofu.tpl -- make generate
op run --env-file .env.pve-opentofu.tpl -- make validate
op run --env-file .env.pve-opentofu.tpl -- make pve-preflight PVE_HOST=cohe PVE_SSH_USER=pve-ops
op run --env-file .env.pve-opentofu.tpl -- make pve-health
op run --env-file .env.pve-opentofu.tpl -- make packer-build PVE_HOST=cohe
op run --env-file .env.pve-opentofu.tpl -- make plan STORAGE_ID=images
op run --env-file .env.pve-opentofu.tpl -- make apply STORAGE_ID=images PVE_HOST=cohe PVE_SSH_USER=pve-ops
op run --env-file .env.pve-opentofu.tpl -- make verify-guests
op run --env-file .env.pve-opentofu.tpl -- make verify-guests-syntax
op run --env-file .env.pve-opentofu.tpl -- make ansible-check
```

`make generate` renders committed outputs from YAML. `make validate` validates
source YAML, generated inventory, and OpenTofu config. `make plan` renders
local cloud-init snippets only. For VMs with NICs this includes both user-data
and network-config snippets plus manifest entries. `make apply` uploads and
verifies all manifest-recorded snippets before applying OpenTofu changes.
`make pve-preflight` is the explicit read-only
PVE readiness check and `make pve-check-pve` is a compatibility alias. Guest
verification is separate and read-only: `make verify-guests` (or root
`make pve-verify-guests`) invokes the Ansible-first playbook with the generated
inventory plus the local SSH agent or 1Password SSH Agent. `STORAGE_ID`,
`PVE_HOST`, and `PVE_SSH_USER` are intentionally explicit inputs; the Makefile
does not provide environment-specific defaults for them.

`make pve-health` is the explicit read-only cluster health check. It uses only
the `TF_VAR_pve_*` API variables from `.env.pve-opentofu.tpl` and no SSH
settings. Invoke it as:

```bash
op run --env-file .env.pve-opentofu.tpl -- make pve-health
```

Manual equivalent:

```bash
export TF_VAR_pve_endpoint=...
export TF_VAR_pve_api_username=...
export TF_VAR_pve_api_token_id=...
export TF_VAR_pve_api_token_secret=...
export TF_VAR_pve_insecure=true
make pve-health
```

`pve-health` stays outside `make check`, `validate`, `check-pve`, and cloud CI.
It reports CPU >90% warn, memory >90% warn, rootfs >90% warn / >98% fail,
and datastore >85% warn / >95% fail. Long-lived VMs missing or stopped warn;
ephemeral lab VMs missing or stopped do not warn solely for that state.

`make pve-preflight` uses the PVE API token variables from
`.env.pve-opentofu.tpl` and should normally be invoked as:

```bash
op run --env-file .env.pve-opentofu.tpl -- make pve-preflight
```

That command stays outside `make check` and outside cloud CI.

Cluster inventory drives the Ansible login user, cloud-init VM users, and the
snippet storage role/prefix used for rendered user-data files.

PVE guest verification must use the generated inventory at
`ansible/inventories/generated/pve.yml`; it does not rely on the default
`ansible.cfg` inventory. The generated inventory uses `ansible_user: ops`,
become settings, and no embedded secrets.

Guest verification results:

- `PASS` — reachable guest matches the declared runtime expectations.
- `WARN` — the guest is offline/unreachable or DNS is mismatched, but no hard
  failure was found.
- `FAIL` — a reachable guest violates a hard read-only check.
- `SKIP` — there are no declared guests in the generated inventory group.

Guest verification stays outside `make check` and GitHub Actions cloud CI.

Guest bootstrap is a separate Ansible step that follows the cloud-init render:

1. OpenTofu renders the guest identity and network inputs.
2. `make pve-bootstrap-guests` applies the shared `vm_baseline` role.
3. `make pve-verify-guests` performs the read-only follow-up check.

Bootstrap uses the generated `pve_vms` inventory, the inventory-provided `ops`
SSH user, and sudo escalation through the same generated metadata. It does not
mutate PVE lifecycle state, does not manage private keys, and does not edit
guest network configuration in the first version; network checks are report-only.

Ordinary VMs and future K3s nodes can reuse the same `vm_baseline` role as long
as they follow the generated inventory contract for hostname and network
identity.

Example commands:

```bash
op run --env-file .env.pve-opentofu.tpl -- make pve-bootstrap-guests-syntax
op run --env-file .env.pve-opentofu.tpl -- make pve-bootstrap-guests ANSIBLE_LIMIT=dev-web-01
op run --env-file .env.pve-opentofu.tpl -- make pve-bootstrap-guests
op run --env-file .env.pve-opentofu.tpl -- make pve-verify-guests
```

The provider uses `bpg/proxmox` `~> 0.109.0` with `ssh { agent = true username = "pve-ops" }` and token-based API auth.

## Safety notes

- Long-lived VMs are split into a separate module call with `prevent_destroy = true`.
- Ephemeral/lab VMs are intentionally not protected by default.
- Passthrough VMs are provisioned through `hostpci` resource mappings and remain in Section 5 scope; no raw PCI paths are accepted.
- Passthrough source YAML may optionally set `device_override` to pin a specific `hostpciN`; otherwise devices are auto-assigned per VM order.
- HA stays disabled for passthrough VMs, and this module does not move VMs between nodes or mutate host IOMMU/VFIO state.
- See `docs/runbooks/pve-pci-passthrough-readiness.md` for the host-side readiness checklist.
- Future TODO: manage PCI resource mappings with `bpg/proxmox` `proxmox_hardware_mapping_pci` from a separate high-privilege bootstrap root such as `infra/tofu/pve-mappings/`; keep this VM lifecycle root limited to consuming mapping names.
- `initialization[0].user_data_file_id` and `initialization[0].network_data_file_id` drift is ignored because the provider can otherwise churn externally managed cloud-init snippets.
- OpenTofu manages VM lifecycle only. It does not create `pve-ops@pve`, its tokens, or the bootstrap ACLs.
- The workflow does not create or modify PVE bridges, VLAN devices, SDN zones,
  OPNsense interfaces, switch ports, firewall rules, DNS records, or post-boot
  guest network state.
- DNS verification in Section 6 is resolver-config only; it checks guest
  nameserver entries and does not manage external DNS records or name
  resolution.
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

Section 4A renders runtime cloud-init snippets for each VM, uploads them into
isolated NFS-backed `images` snippets storage, and references them with
`user_data_file_id` plus `network_data_file_id` when a VM needs explicit
network-config.

- Snippet name: `opentofu-vm-<vmid>-user-data.yml`
- File ID: `images:snippets/opentofu-vm-<vmid>-user-data.yml`
- Multi-NIC network-config snippet name: `opentofu-vm-<vmid>-network-config.yml`
- Multi-NIC network-config file ID: `images:snippets/opentofu-vm-<vmid>-network-config.yml`
- Cloud-init media/drive datastore: the `memory` role/datastore. Snippets stay
  on `images`, while VM root/EFI disks and cloud-init drive media use `memory`.
- Retention: snippets stay in storage for the VM lifetime; do not delete them immediately after upload.

Use `op run --env-file .env.pve-opentofu.tpl -- make render-cloud-init STORAGE_ID=images` to create local snippets plus `manifest.json`. The legacy `render-user-data` target is kept as a compatibility alias. `make plan` stays local. `make apply` renders once, then `upload-cloud-init` and `verify-cloud-init` consume the existing manifest/snippet files before the OpenTofu apply. Compatibility aliases `upload-user-data` and `verify-user-data` remain available.

Required runtime env vars from `op run` (driven by the inventory-defined cloud-init users):

- `PVE_VM_CLEMON_PASSWORD`
- `PVE_VM_CLEMON_PUBLIC_KEY`
- `PVE_VM_OPS_PASSWORD`
- `PVE_VM_OPS_PUBLIC_KEY`

The runtime helper hashes passwords locally, writes only ignored cache files, and never logs plaintext secrets or password hashes.

Upload and verify targets read the existing manifest and exact local snippet files; they do not rerender user-data or network-config. Verify passes the manifest checksum to the host-side wrapper, which checks remote content before accepting it.

Snippet upload and verify use the audited host-side wrapper `/usr/local/sbin/astra-pve-snippet-upload`; it does not rely on broad `sudo install` privileges. The wrapper installs files `0600` on non-NFS snippet storage and `0644` on NFS-backed storage to remain readable when root-squash or server-side ownership mapping is in effect. This is an intentional tradeoff for the isolated `images` NFS storage; do not use this mode on broadly shared or untrusted storage. Keep `STORAGE_ID` aligned with `local.snippets_datastore`.

## Live-test notes

- Section 4/4A was live-tested with VMID `500` (`dev-web-01`) on `cohe`, attached to `br_dev` with static IP `10.10.0.20/24`, then destroyed with a targeted OpenTofu destroy.
- PVE 9 required `AstraAutomation` on both the parent user `pve-ops@pve` and the privilege-separated token `pve-ops@pve!opentofu`.
- `AstraAutomation` also required `SDN.Use` for the `br_dev` SDN bridge check.
- Guest SSH for `ops` depends on the corresponding keys being available in the
  local SSH agent or 1Password SSH Agent; the workflow does not read repository
  private keys.
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

## Local state backup helper

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
