# Astra PVE OpenTofu Root

This is Astra's environment-owned OpenTofu root. It composes the reusable
`automation/opentofu/modules/pve-cloudinit-vm` module; it does not own that
module or PVE-node/Packer mechanisms.

The root Makefile is the supported operator facade. It generates
`environments/astra/generated/opentofu/pve.tfvars.json` and passes it with
`-var-file`; the filename is deliberately not an auto-loaded tfvars file.

## Inputs and generated data

- Source inventory: `environments/astra/inventory/pve-cluster.yml` and
  `environments/astra/inventory/vms.yml`.
- Generated OpenTofu input:
  `environments/astra/generated/opentofu/pve.tfvars.json`.
- Generated guest inventory:
  `environments/astra/generated/ansible/pve.yml`.
- Runtime template:
  `environments/astra/runtime/.env.pve-opentofu.tpl`.

Run offline checks from the repository root:

```bash
make generate
make check
```

Online and mutation-capable actions remain explicit:

```bash
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-health
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-preflight
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-plan STORAGE_ID=images
```

`pve-plan`, `pve-apply`, and `pve-destroy` may write local state at
`environments/astra/opentofu/pve/terraform.tfstate`. State is ignored. The
pre-cutover state in `infra/tofu/pve/` was intentionally discarded and was not
migrated; ignored `.cache/tofu-state-backups/` remains operator-owned and is
not an input to this root.

PVE bridge configuration, PVE identities, API tokens, PCI/IOMMU host setup,
Packer node bootstrap, DNS, firewall, and K3s are outside this root's scope.
