# PVE State, Cache, and Secret Operations

This runbook describes local operator data. It does not add a live check,
recovery gate, plan, apply, or destroy action to the offline default gate.

| Area | Path | Rule |
| --- | --- | --- |
| Future local state | `environments/astra/opentofu/pve/terraform.tfstate` | Ignored; never commit. |
| State backups | `.cache/tofu-state-backups/` | Ignored, sensitive, and operator-owned. |
| Cloud-init runtime output | `.cache/pve-cloud-init/user-data/` | Ignored and sensitive-adjacent. |
| Packer runtime cache | `.cache/packer/` | Ignored runtime cache. |
| PVE generated input | `environments/astra/generated/opentofu/pve.tfvars.json` | Committed only when non-secret. |
| Generated Ansible inventory | `environments/astra/generated/ansible/pve.yml` | Committed only when non-secret. |
| Runtime PVE template | `environments/astra/runtime/.env.pve-opentofu.tpl` | Commit 1Password references, never resolved values. |

The old `infra/tofu/pve/terraform.tfstate*` files were discarded during the
repository-layer cutover. They were not copied or migrated. Existing ignored
backup cache contents were deliberately left untouched and must not be used as
an implicit state input for the relocated root.

## Future state operations

Use the root facade for future state created under the relocated root:

```bash
make pve-backup-state
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-plan STORAGE_ID=images
```

The plan/apply/destroy targets take an opportunistic local backup before and,
for successful mutation, after the operation. Review every live command and
its explicit target context. A backup is a local file-recovery aid, not proof
of infrastructure correctness and not a replacement for a manual recovery
decision.

## Secret and cache rules

- Inject runtime credentials with `op run --env-file ...`; do not export or
  commit resolved secret values.
- Treat rendered cloud-init snippets, manifests, state, and backups as
  sensitive-adjacent.
- Do not delete cache or backup data automatically as part of this repository
  refactor. Clean it only when no related operator workflow is running.
- Run `make generate` and `make check` before an intentional online operation;
  online checks and mutations stay outside the default gate.
