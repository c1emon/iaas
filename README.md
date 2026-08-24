# Astra Infrastructure Operator Manual

This repository is the source of truth for Astra infrastructure automation.
Start here for operator workflow; use `docs/` and module READMEs for deeper
implementation detail. No real secrets are committed.

The safest first workflow is the offline validation gate:

```bash
uv sync --locked --dev
pnpm install --frozen-lockfile
make generate && make check-generated && make check
```

`make check` is offline-only: it checks generated output, tests, inventory YAML,
Python types, self-contained PVE/OPNsense Ansible playbooks and the VM baseline
role, strict OpenSpec contracts, and OpenTofu formatting/validation. It does not
need runtime credentials or contact infrastructure.

That gate does not require runtime secrets, live PVE, OPNsense, switch, guest,
Packer build, OpenTofu apply/destroy, or Ansible mutation access.

## Capability map

- `docs/` — architecture, operations, decisions, generated references.
- `inventory/` — operator-authored source of truth for PVE, VMs, services, and foundation recovery metadata.
- `infra/tofu/` — PVE VM lifecycle and local state handling.
- `infra/packer/` — Debian 13 template build helper.
- `ansible/` — OPNsense, switch, and PVE guest workflows.
- `scripts/` — helper scripts and validation utilities.

## Safety classes

| Class | Meaning | Examples |
| --- | --- | --- |
| Offline-safe | No live infrastructure access, no runtime secrets, no mutation. | `make generate`, `make check-generated`, `make check`, `make foundation-check`, `make secret-scan`, `make pve-ansible-syntax` |
| Online read-only | Contacts live infrastructure and requires runtime context, but should not change state. | `make foundation-health`, `make pve-health`, `make pve-preflight`, `make pve-verify-guests`, `ansible/playbooks/opnsense/readonly.yml`, `ansible/playbooks/switches/readonly-facts.yml` |
| Mutation-capable | May create, update, delete, upload, reboot, or otherwise change live state. | `make pve-apply`, `make pve-destroy`, `make pve-packer-build`, `ansible/playbooks/opnsense/manage-*.yml`, `ansible/playbooks/switches/config-plan.yml` when `switch_config_apply=true` |

## Source of truth

| File | Purpose |
| --- | --- |
| `inventory/pve-cluster.yml` | Cluster defaults, placement rules, template inputs, and cloud-init user material references. |
| `inventory/vms.yml` | VM declarations, lifecycle class, networking, boot, and passthrough intent. |
| `inventory/services.yml` | Declared service catalog and endpoint review metadata. |
| `inventory/foundation.yml` | Foundation hosts, recovery-critical services, restore order, health checks, break-glass references, and storage-network facts. |

## Committed generated outputs

| File | Sensitivity expectation |
| --- | --- |
| `infra/tofu/pve/generated.auto.tfvars.json` | Reviewable non-sensitive generated input. |
| `ansible/inventories/generated/pve.yml` | Reviewable non-sensitive generated inventory. |
| `docs/generated/pve-vms.md` | Reviewable non-sensitive VM summary. |
| `docs/generated/services.md` | Reviewable non-sensitive service summary. |
| `docs/generated/foundation-recovery.md` | Reviewable non-sensitive foundation recovery reference. |
| `infra/packer/proxmox/debian-13/template-build.env` | Committed non-secret defaults only. |

## Common workflows

| Workflow | Safety class | Entry point |
| --- | --- | --- |
| Generate committed outputs | Offline-safe | `make generate` |
| Validate repository shape | Offline-safe | `make generate && make check-generated && make check` |
| PVE health / readiness | Online read-only | `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-health` / `make pve-preflight` |
| PVE guest verification | Online read-only | `make pve-verify-guests` |
| PVE VM lifecycle planning | Online read-only | `make pve-plan` |
| PVE VM lifecycle apply/destroy | Mutation-capable | `make pve-apply`, `make pve-destroy` |
| PVE template build | Mutation-capable | `make pve-packer-build` and `infra/packer/proxmox/debian-13/README.md` |
| OPNsense read-only review | Online read-only | `docs/opnsense-management.md` and `ansible/playbooks/opnsense/README.md` |
| OPNsense management | Mutation-capable | `ansible/playbooks/opnsense/manage-*.yml` via `ansible/README.md` |
| Switch fact collection | Online read-only | `ansible/playbooks/switches/README.md` |
| Switch config apply | Mutation-capable | `ansible/playbooks/switches/README.md` and `ansible/roles/switch_config/README.md` |
| Service metadata review | Offline-safe | `docs/service-metadata.md` and `docs/generated/services.md` |
| Foundation recovery review | Offline-safe / Online read-only | `make foundation-check`, `docs/generated/foundation-recovery.md`; explicit live probes via `make foundation-health` |

## Runtime parameters and secret injection

| Area | Runtime parameters | Secret injection |
| --- | --- | --- |
| PVE OpenTofu | `TF_VAR_pve_*`, `PVE_HOST`, `PVE_SSH_USER`, `STORAGE_ID` | `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- ...`; cloud-init user vars come from the same template via `PVE_VM_*` variables. |
| PVE template build | `PVE_HOST`, `FORCE_REPLACE`, `TEMPLATE_DEBUG`, `BUILD_*` inputs from `template-build.env` | Non-secret defaults are committed; credentials stay outside the repo and are supplied at runtime. |
| OPNsense | `OPNSENSE_API_KEY`, `OPNSENSE_API_SECRET` | `op run --env-file .env.opnsense.tpl -- ...` |
| Switches | `SWITCH_SSH_USER`, `SWITCH_SSH_PASSWORD`, `SWITCH_SSH_PORT` | `op run --env-file .env.switch.tpl -- ...` |

Runtime secrets, private keys, local state, cache files, raw exports, and
resolved credential files are not safe to commit. Use
[`docs/pve-state-cache-secrets.md`](docs/pve-state-cache-secrets.md) for the
detailed state/cache/secret handling runbook.

## Documentation map

- Start here: [`docs/README.md`](docs/README.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- State, cache, and secrets: [`docs/pve-state-cache-secrets.md`](docs/pve-state-cache-secrets.md)
- OPNsense management: [`docs/opnsense-management.md`](docs/opnsense-management.md)
- Service metadata: [`docs/service-metadata.md`](docs/service-metadata.md)
- Foundation recovery reference: [`docs/generated/foundation-recovery.md`](docs/generated/foundation-recovery.md)
- PCI passthrough readiness: [`docs/runbooks/pve-pci-passthrough-readiness.md`](docs/runbooks/pve-pci-passthrough-readiness.md)
- PVE rolling maintenance: [`docs/runbooks/pve-rolling-maintenance.md`](docs/runbooks/pve-rolling-maintenance.md)
- Decisions: [`docs/decisions/pve-automation-preflight.md`](docs/decisions/pve-automation-preflight.md), [`docs/decisions/iaas-automation-roadmap-research.md`](docs/decisions/iaas-automation-roadmap-research.md)
- Historical / remediation planning: [`docs/review-remediation-roadmap.md`](docs/review-remediation-roadmap.md)
- Current roadmap and backlog: [`docs/roadmap.md`](docs/roadmap.md)
- Detailed module READMEs: [`infra/tofu/pve/README.md`](infra/tofu/pve/README.md), [`infra/packer/proxmox/debian-13/README.md`](infra/packer/proxmox/debian-13/README.md), [`ansible/README.md`](ansible/README.md), [`ansible/playbooks/opnsense/README.md`](ansible/playbooks/opnsense/README.md), [`ansible/playbooks/switches/README.md`](ansible/playbooks/switches/README.md), [`ansible/roles/switch_config/README.md`](ansible/roles/switch_config/README.md), [`scripts/README.md`](scripts/README.md)
