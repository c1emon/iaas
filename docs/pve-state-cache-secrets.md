# PVE State, Cache, and Secret Operations

This runbook is the local operator contract for PVE automation state, ignored
runtime cache files, generated review artifacts, and runtime secret injection.
It documents existing helpers; it does not add any online preflight, plan,
apply, destroy, Packer build, guest SSH verification, or recovery mutation to
the default validation path.

## Path inventory

| Area | Path | Source control | Sensitivity expectation |
| --- | --- | --- | --- |
| PVE OpenTofu local state | `infra/tofu/pve/terraform.tfstate` | Ignored | Sensitive local state; keep private to the operator workstation. |
| PVE state backups | `.cache/tofu-state-backups/` | Ignored | Sensitive snapshots of local state. |
| Rendered cloud-init snippets | `.cache/pve-cloud-init/user-data/` | Ignored | May include password hashes, SSH keys, hostnames, IPs, user-data, and network-config. |
| Cloud-init snippet manifest | `.cache/pve-cloud-init/user-data/manifest.json` | Ignored | Sensitive-adjacent runtime metadata with snippet kinds, names, VM identity, checksums, and source tfvars provenance. |
| Local Packer cache | `.cache/packer/` | Ignored | Runtime cache only; current remote wrapper caches on the PVE node under `/var/cache/astra/packer`. |
| OPNsense exports/snapshots | `exports/opnsense/` | Ignored | Treat as environment-derived and review before sharing. |
| Generated PVE OpenTofu input | `infra/tofu/pve/generated.auto.tfvars.json` | Committed | Reviewable non-sensitive generated artifact. |
| Generated PVE Ansible inventory | `ansible/inventories/generated/pve.yml` | Committed | Reviewable non-sensitive generated artifact. |
| Generated PVE VM docs | `docs/generated/pve-vms.md` | Committed | Reviewable non-sensitive generated artifact. |
| Generated service metadata docs | `docs/generated/services.md` | Committed | Reviewable non-sensitive generated artifact. |
| Packer template defaults | `infra/packer/proxmox/debian-13/template-build.env` | Committed | Non-sensitive defaults; runtime host and credentials stay outside the file. |
| PVE/OpenTofu env template | `infra/tofu/pve/.env.pve-opentofu.tpl` | Committed template | 1Password references only; resolved values are secrets. |
| OPNsense env template | `.env.opnsense.tpl` | Committed template | 1Password references only; resolved values are secrets. |
| Switch env template | `.env.switch.tpl` | Committed template | 1Password references only; resolved values are secrets. |

## Local OpenTofu state ownership

The first PVE lifecycle workflow uses local OpenTofu state owned by the operator
running the command:

- State path: `infra/tofu/pve/terraform.tfstate`
- Backup directory: `.cache/tofu-state-backups/`
- Root helper: `make pve-backup-state`
- PVE-module helper: `make -C infra/tofu/pve backup-state`

Run `make pve-backup-state` before any explicit plan/apply-like workflow that
could depend on or modify local state, and again after successful mutation if
the workflow does not already do so. The PVE Makefile currently backs up state
around `plan`, `apply`, and `destroy`; the explicit helper exists so operators
can snapshot state before experiments, manual state inspection, provider
upgrades, or recovery work.

Backups are timestamped under `.cache/tofu-state-backups/`. They are ignored by
Git and should be handled as sensitive because state can contain provider data,
resource identifiers, rendered values, and other environment-specific details.

## Local state restore procedure

Restoring local state is a file recovery step only. It must not automatically
run `plan`, `apply`, `destroy`, PVE API calls, guest SSH checks, or any other
infrastructure mutation.

1. Stop and inspect the failed workflow output.
2. Do not run a corrective `apply` or `destroy` as the first recovery action.
3. List available local backups in `.cache/tofu-state-backups/` and choose the
   snapshot taken before the unintended local state change.
4. Copy the current `infra/tofu/pve/terraform.tfstate` aside to a separate local
   recovery file if it still exists.
5. Copy the selected backup to `infra/tofu/pve/terraform.tfstate`.
6. Run offline checks only, such as `make check-generated` or `make tofu-validate`,
   to confirm repository and OpenTofu configuration shape.
7. Review any later `make pve-plan` manually before considering live mutation.

If state and live infrastructure may have diverged, pause and decide on a manual
operator recovery plan. Do not encode automatic mutation as part of restore.

## `.cache` cleanup and sensitivity rules

Known repository cache paths for these workflows are:

- `.cache/tofu-state-backups/`
- `.cache/pve-cloud-init/user-data/`
- `.cache/pve-cloud-init/user-data/manifest.json`
- `.cache/packer/`

Cleanup is safe when no related workflow is running:

```bash
rm -rf .cache/pve-cloud-init/user-data .cache/packer
```

Only delete `.cache/tofu-state-backups/` after confirming no backup is needed for
local recovery. Never commit `.cache` contents. Treat state backups, rendered
cloud-init snippets, and their manifest/checksum files as sensitive-adjacent;
rendered artifacts may contain password hashes, authorized SSH keys, usernames,
checksums, host identity data, and guest network topology.

## Runtime secret injection conventions

Commit environment templates with 1Password references, not resolved secret
values. Run credentialed workflows with `op run --env-file ... -- <command>` or
explicit `op read` calls documented by the workflow.

| Workflow | Runtime convention |
| --- | --- |
| PVE OpenTofu plan/apply/destroy | `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-plan` (or `pve-apply`/`pve-destroy`) |
| PVE cloud-init users | Same PVE env template provides VM user password/public-key material consumed by snippet rendering. |
| Packer/template build | Use the generated non-secret `template-build.env` plus explicit runtime values such as `PVE_HOST`; inject any required credentials through 1Password or the operator shell, not committed files. |
| OPNsense workflows | `op run --env-file .env.opnsense.tpl -- uv run ansible-playbook ...` |
| Switch workflows | `op run --env-file .env.switch.tpl -- uv run ansible-playbook ...` |

Plaintext secrets, private keys, API token secrets, password hashes, SSH private
keys, and environment-specific credential values must not be committed. If a
generated file unexpectedly contains credential-like material, treat it as unsafe:
stop, remove the value from the source/runtime path, regenerate, and review the
diff before committing.

## Generated outputs that are committed

The following generated outputs are intended to be committed and reviewed:

- `infra/tofu/pve/generated.auto.tfvars.json`
- `ansible/inventories/generated/pve.yml`
- `docs/generated/pve-vms.md`
- `docs/generated/services.md`
- `infra/packer/proxmox/debian-13/template-build.env`

These files must remain non-sensitive. They may contain inventory names,
networks, VM IDs, non-secret defaults, and generated structure needed for code
review. They must not contain resolved API token secrets, private keys, password
hashes, plaintext passwords, or local-only state data.

## Pre-operation and recovery checklist

Before explicit online or mutation-capable PVE workflows (`make pve-plan`,
`make pve-apply`, `make pve-destroy`, `make pve-packer-build`, cloud-init upload
or verify helpers, or guest verification):

- Confirm the command is intentionally outside default `make check`.
- Run `make generate` and review generated output diffs.
- Run `make check` for the default offline gate.
- Run `make pve-backup-state` when local OpenTofu state exists or may be used.
- Confirm the correct `op run --env-file ...` template and 1Password account are
  in use for the workflow.
- Confirm ignored cache paths do not contain stale cloud-init snippets or state
  backups that could confuse the operation.
- Review the live command and target context before pressing enter.
- For explicit-NIC VMs that declare at least one NIC, confirm the rendered
  manifest includes both `user-data` and `network-config` snippets and that
  upload/verify consumes the manifest rather than rerendering.

After a failed local workflow:

- Preserve logs and current local state before overwriting anything.
- Use the restore procedure above for local state recovery if needed.
- Clean rendered cloud-init or Packer cache files only when no workflow is using
  them.
- Re-run offline validation before any later live plan/apply-like command.
- Do not use automatic infrastructure mutation as a recovery shortcut.
