# Astra Infrastructure Operator Manual

This repository separates one concrete environment from reusable automation.
No real secrets, local state, or cache contents are committed.

```bash
uv sync --locked --dev
make generate
make check
```

`make check` is offline-only. It validates generated outputs, tests, YAML,
Python types, Ansible, OpenTofu shape, and OPNsense desired state. It neither
contacts nor changes infrastructure.

## Repository layers

- `environments/astra/` — Astra-owned inventory, Ansible data, runtime
  templates, OpenTofu root, and committed generated outputs.
- `automation/` — reusable Python (`src/iaas_automation`), Ansible, OpenTofu
  modules, Packer, and PVE-node mechanisms.
- `platform/` — reserved for future in-cluster platform automation; no K3s or
  cluster platform capability is implemented here.
- `tests/` — repository tests.

## Astra sources and generated outputs

| Source | Purpose |
| --- | --- |
| `environments/astra/inventory/pve-cluster.yml` | PVE topology, networks, storage roles, templates, VMID policy, and PCI mappings. |
| `environments/astra/inventory/vms.yml` | VM declarations and lifecycle intent. |
| `environments/astra/inventory/services.yml` | Service metadata. |
| `environments/astra/inventory/foundation.yml` | Foundation recovery metadata. |
| `environments/astra/ansible/` | Environment inventory, group variables, and desired-state variables. |

Generated, reviewable non-secret artifacts are under
`environments/astra/generated/{opentofu,ansible,packer,docs}/`.

## Safety classes

| Class | Examples |
| --- | --- |
| Offline-safe | `make generate`, `make check`, `make secret-scan`, `make pve-ansible-syntax` |
| Online read-only | `make pve-health`, `make pve-preflight`, `make pve-verify-guests`, `make foundation-health` |
| Mutation-capable | `make pve-plan`, `make pve-apply`, `make pve-destroy`, `make pve-packer-build`, Ansible management playbooks |

## Runtime entrypoints

Runtime templates are environment-owned:

- `environments/astra/runtime/.env.pve-opentofu.tpl`
- `environments/astra/runtime/.env.opnsense.tpl`
- `environments/astra/runtime/.env.switch.tpl`

For example:

```bash
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-health
```

Use the root Makefile as the supported operator facade. It passes the Astra
source and generated paths explicitly to `iaas_automation`; old `scripts.*`
imports and nested Makefiles are not supported.

## Documentation

- [Documentation index](docs/README.md)
- [PVE state, cache, and secret handling](docs/pve-state-cache-secrets.md)
- [Astra OpenTofu root](environments/astra/opentofu/pve/README.md)
- [Reusable Ansible automation](automation/ansible/README.md)
- [Future platform boundary](platform/README.md)
