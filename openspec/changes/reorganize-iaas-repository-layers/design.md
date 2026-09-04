## Context

The repository currently mixes Astra-specific data, reusable automation, generated files, and future cluster-platform design. This change makes those responsibilities visible without adding a new orchestration framework.

## Goals

- Put Astra-specific configuration under `environments/astra/`.
- Put reusable mechanisms under `automation/`.
- Make the PVE cluster and VM inventories authoritative for PVE topology and VM lifecycle facts.
- Move the Python package from `scripts` to `automation/src/iaas_automation`.
- Keep the root Makefile as the operator entrypoint and preserve existing command safety.
- Reserve `platform/` for future cluster automation documentation only.
- Perform a hard cutover without compatibility paths for the moved repository layout or `scripts.*` package.

## Non-goals

- Implementing K3s, Flux, Cilium, CSI, Gateway, or application deployment.
- Building a general multi-environment selector or testing framework.
- Renaming existing wrappers, installed commands, runtime variables, PVE identities, or 1Password items merely to make them generic.
- Reorganizing all ignored caches, exports, or observations.
- Migrating current OpenTofu state or backups into the new root.
- Rewriting historical OpenSpec archives.
- Accessing or mutating live infrastructure as validation for this refactor.

## Target layout

```text
environments/
  astra/
    inventory/
    ansible/
      inventory.yml
      group_vars/
      vars/
    runtime/
    generated/
      opentofu/
      ansible/
      packer/
      docs/
    opentofu/
      pve/

automation/
  src/iaas_automation/
  ansible/
    ansible.cfg
    requirements.yml
    playbooks/
    roles/
  opentofu/modules/
  packer/
  pve-node/

platform/
  README.md

docs/
openspec/
tests/
Makefile
pyproject.toml
```

`environments/astra/` owns concrete Astra composition and generated deployment inputs. `automation/` owns reusable implementation. The Astra OpenTofu root remains environment-owned because it composes the reusable modules for that environment. `platform/` is documentation-only in this change.

## Inventory authority

`environments/astra/inventory/pve-cluster.yml` is authoritative for the PVE cluster topology, networks, storage roles, templates, VMID policy, and PCI mappings. `environments/astra/inventory/vms.yml` is authoritative for VM declarations and lifecycle intent.

Repository validation, rendering, health/preflight expectations, and environment deployment inputs derive their PVE/VM facts from these declarations. Validation continues to enforce structure, references, uniqueness, network relationships, provider limits, lifecycle safety, and secret exclusion. Existing host-side wrapper protection envelopes remain independent defense-in-depth limits; this change does not redesign them.

Service and foundation inventories keep their existing domain ownership and reference VMs where required. Ansible inventory and variables remain authored environment data. This change does not impose a repository-wide rule that every repeated value must be generated from one global source; it only removes conflicting PVE/VM facts where the current automation depends on them.

## Path migration

| Current path | Target path |
| --- | --- |
| `inventory/*.yml` | `environments/astra/inventory/*.yml` |
| `ansible/inventories/homelab.yml` | `environments/astra/ansible/inventory.yml` |
| `ansible/inventories/group_vars/**` | `environments/astra/ansible/group_vars/**` |
| `ansible/vars/opnsense/**`, `ansible/vars/switches/**` | `environments/astra/ansible/vars/**` |
| `.env.opnsense.tpl`, `.env.switch.tpl`, `infra/tofu/pve/.env.pve-opentofu.tpl` | `environments/astra/runtime/` |
| `infra/tofu/pve/generated.auto.tfvars.json` | `environments/astra/generated/opentofu/pve.tfvars.json` |
| `ansible/inventories/generated/**` | `environments/astra/generated/ansible/**` |
| `infra/packer/proxmox/debian-13/template-build.env` | `environments/astra/generated/packer/debian-13.env` |
| `docs/generated/**` | `environments/astra/generated/docs/**` |
| `infra/tofu/pve/*.tf`, lock file, and README | `environments/astra/opentofu/pve/` |
| `infra/tofu/pve/Makefile` | removed after required targets move to the root Makefile |
| `infra/tofu/modules/**` | `automation/opentofu/modules/**` |
| `infra/packer/**` excluding generated input | `automation/packer/**` |
| `infra/pve-node/**` | `automation/pve-node/**` |
| root and nested Ansible configuration plus reusable `ansible/**` | one `automation/ansible/ansible.cfg` and reusable `automation/ansible/**` |
| Python packages under `scripts/` | `automation/src/iaas_automation/**` |
| `scripts/validate_pve_inventory.py` | removed; compatibility wrapper is not migrated |
| `scripts/README.md` | merged into current automation documentation |
| `scripts/tests/**`, `ansible/tests/**` | `tests/**` |
| `infra/tofu/pve/terraform.tfstate*` | discarded; no target |
| `.cache/tofu-state-backups/**` | left ignored and untouched; not used by the relocated root |
| `terraform/README.md`, orphaned `pnpm-workspace.yaml` | removed after confirming they have no current consumer |

Existing ignored cache and export locations remain unchanged unless a moved consumer requires a path update. Existing external wrapper names, runtime variables, identities, and secret references remain unchanged.

## Python and command boundary

The supported Python package becomes `iaas_automation`; the old `scripts` package is removed. Reusable CLIs accept the source and output paths needed by their work. The root Makefile passes the Astra paths explicitly and remains the canonical operator facade. This change does not introduce `ENVIRONMENT`, a second synthetic environment, or a requirement to run every CLI from outside the repository.

## State handling

State files in the old OpenTofu root are not copied into the new root and are discarded before that root is moved. Existing ignored backup caches remain untouched and are not inputs to the relocated root. The relocated Astra OpenTofu root therefore starts without migrated state.

No state-migration or recovery gate is required for this cutover. Future state created at the new root remains ignored and follows the existing state safety documentation.

## Safety and validation

The existing operation classes remain unchanged:

- Offline-safe checks do not require infrastructure credentials or live access.
- Online read-only commands may inspect infrastructure and write ignored observations.
- Mutation-capable commands remain explicit and outside the aggregate offline gate.

After relocation, the existing generation/check workflow and offline gate must still pass. Generated JSON and YAML must keep their existing schemas and meanings for unchanged inventory; documentation and provenance paths may change. Review is based on ordinary diffs and existing tests, not a new hash or exhaustive artifact-parity framework.

Current code, CI, docs, and this change's deltas use the new paths. Base specs receive those deltas when the change is archived; historical archives remain unchanged and need no permanent allowlist validator.

## Migration strategy

1. Record the current path map and run the existing offline baseline.
2. Remove concrete Astra PVE/VM policy from reusable validation where it currently exists.
3. Move the Python package and tests, updating imports and entrypoints without compatibility shims.
4. Move Astra data, generated artifacts, runtime templates, and the OpenTofu root; update all consumers.
5. Move reusable Ansible, OpenTofu modules, Packer, and PVE-node automation. The relocated Packer trigger requires the generated environment file to be selected explicitly through `TEMPLATE_BUILD_ENV`; it has no sibling-file fallback.
6. Remove old supported paths, update docs and configuration, and run final offline/OpenSpec/GitNexus checks.
