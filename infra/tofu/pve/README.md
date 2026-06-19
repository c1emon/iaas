# OpenTofu PVE VM lifecycle

This directory is the root module for Section 4 of `add-pve-automation-foundation`.

## Inputs

- `generated.auto.tfvars.json` is loaded automatically.
- Runtime secrets are injected with `op run` using `.env.pve-opentofu.tpl`.
- No secrets are committed.
- `.env.pve-opentofu.tpl` sets `TF_VAR_pve_insecure=true` for the common PVE
  self-signed certificate case. Remove or override it if the cluster uses a
  trusted certificate chain.

## State

- Local state path: `terraform.tfstate`
- Backups: `.cache/tofu-state-backups/`
- Existing VMs are intentionally out of scope.
- VM declarations with passthrough are intentionally deferred until Section 5.

## Usage

```bash
op run --env-file .env.pve-opentofu.tpl -- tofu init -backend=false
op run --env-file .env.pve-opentofu.tpl -- tofu validate
op run --env-file .env.pve-opentofu.tpl -- make plan
```

The provider uses `bpg/proxmox` `~> 0.109.0` with `ssh { agent = true username = "pve-ops" }` and token-based API auth.

## Safety notes

- Long-lived VMs are split into a separate module call with `prevent_destroy = true`.
- Ephemeral/lab VMs are intentionally not protected by default.
- Passthrough VMs are excluded from this section and left for Section 5.
- `initialization[0].user_data_file_id` drift is ignored because the provider can otherwise churn externally managed cloud-init snippets; IP configuration and DNS remain Terraform-managed.
- OpenTofu manages VM lifecycle only. It does not create `pve-ops@pve`, its tokens, or the bootstrap ACLs.

## Section 4A cloud-init flow

Section 4A renders runtime cloud-init user-data snippets for each non-passthrough VM,
uploads them into shared `images` snippets storage, and references them with
`user_data_file_id`.

- Snippet name: `opentofu-vm-<vmid>-user-data.yml`
- File ID: `images:snippets/opentofu-vm-<vmid>-user-data.yml`
- Retention: snippets stay in storage for the VM lifetime; do not delete them immediately after upload.

Use `op run --env-file .env.pve-opentofu.tpl -- make render-user-data` to create local snippets and `op run --env-file .env.pve-opentofu.tpl -- make upload-user-data` to push them to PVE storage before `make plan` or `make apply`.

Required runtime env vars from `op run`:

- `PVE_VM_CLEMON_PASSWORD`
- `PVE_VM_CLEMON_PUBLIC_KEY`
- `PVE_VM_OPS_PASSWORD`
- `PVE_VM_OPS_PUBLIC_KEY`

The runtime helper hashes passwords locally, writes only ignored cache files, and never logs plaintext secrets or password hashes.

Snippet upload uses the audited host-side wrapper `/usr/local/sbin/astra-pve-snippet-upload`; it does not rely on broad `sudo install` privileges. On NFS/root-squashed snippet storage, the wrapper intentionally does not force `root:root` ownership; it constrains the target path and file mode instead.

## Live-test notes

- Section 4/4A was live-tested with VMID `500` (`dev-web-01`) on `cohe`, attached to `br_dev` with static IP `10.10.0.20/24`, then destroyed with a targeted OpenTofu destroy.
- PVE 9 required `AstraAutomation` on both the parent user `pve-ops@pve` and the privilege-separated token `pve-ops@pve!opentofu`.
- `AstraAutomation` also required `SDN.Use` for the `br_dev` SDN bridge check.
- Guest SSH for `ops` and `clemon` depends on the corresponding keys being available in the local SSH agent or 1Password SSH Agent.

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

Use `make backup-state` before or after apply-like operations. `make apply` and `make destroy` call it automatically.

## Optional smoke checks

Manual validation against a live PVE node can be done later with:

```bash
ssh pve-ops@cohe 'sudo -n /usr/local/sbin/astra-pve-template-build --help'
ssh pve-ops@cohe 'sudo -n /usr/local/sbin/astra-pve-snippet-upload --help'
ssh <existing-admin-login>@cohe 'sudo -n visudo -cf /etc/sudoers.d/astra-pve-template-build'
ssh <existing-admin-login>@cohe 'sudo -n visudo -cf /etc/sudoers.d/astra-pve-snippet-upload'
```

Those checks are outside repository validation and are not required here.
