## Why

Environment-specific configuration, reusable automation, generated outputs, and future platform responsibilities are mixed across `inventory/`, `infra/`, `ansible/`, `scripts/`, and `docs/generated/`. The PVE validator also duplicates Astra topology and policy values that already belong in inventory.

This should be cleaned up before adding K3s. There is no production deployment in use and no legacy OpenTofu state will be carried forward, so the repository can use a direct hard cutover without compatibility paths or state migration.

## What Changes

- Introduce `environments/astra/` for Astra inventory, Ansible environment data, runtime-reference templates, the Astra OpenTofu root, and committed generated outputs.
- Introduce `automation/` for reusable Python, Ansible, OpenTofu modules, Packer, and PVE-node implementation.
- Reserve `platform/` for future in-cluster platform work; this change adds documentation only.
- Rename the Python package from `scripts` to `iaas_automation` under `automation/src/` and update repository callers.
- Make PVE cluster and VM inventory authoritative for repository validation, rendering, expectations, and deployment inputs instead of duplicating Astra values in those paths.
- Keep the root Makefile as the operator entrypoint, update paths, consolidate Ansible configuration, and remove old repository paths without aliases or symlinks.
- Update current documentation and OpenSpec path contracts while leaving historical archives unchanged.
- Start the relocated OpenTofu root without migrated state; discard state files in the old root and leave existing ignored backup caches untouched.

## Capabilities

### New Capabilities

- `iaas-repository-layering`: Defines environment, automation, and platform ownership; PVE/VM inventory authority; and the hard-cutover contract.

### Modified Capabilities

- `pve-automation-foundation`: Uses relocated environment inputs/outputs and inventory-declared PVE policy.
- `pve-inventory-package-organization`: Replaces `scripts.*` with the sole `iaas_automation.*` package and command surface.
- `pve-inventory-validation-structure`: Updates validation imports and current inventory paths.
- `python-common-primitives`: Moves common helpers to `iaas_automation.common`.
- `iaas-validation-entrypoints`: Uses the relocated Astra source and generated paths while preserving offline safety.
- `service-metadata-inventory`: Relocates service and VM sources and generated service documentation.
- `foundation-recovery-checks`: Relocates the foundation source and generated recovery document.
- `pve-state-and-secret-operations`: Documents future local state handling and the decision not to migrate legacy state.
- `switch-cli-readonly-facts`: Relocates the reusable playbook entrypoint.
- `switch-readonly-facts-export-workflow`: Relocates the reusable playbook entrypoint without changing export policy.
- `operator-documentation-entrypoints`: Updates the current source/generated map.
- `iaas-repository-hygiene`: Makes current documentation follow relocated inventory and keeps history historical.

## Impact

- Repository paths, Python imports, tests, Make targets, CI references, current OpenSpec path contracts, current documentation links, templates, ignore rules, and generated consumers are affected.
- `validate_cluster` and `render_outputs` are high-impact call-graph hubs, so the repository-required GitNexus checks and focused tests apply before and after their edits.
- Old supported repository paths and `scripts.*` imports are removed in the same change; no compatibility route whose purpose is to preserve those old surfaces remains.
- Existing wrapper names, runtime variable names, PVE identities, 1Password conventions, cache layout, export layout, and live infrastructure are not redesigned by this change.
- No live infrastructure operation or K3s implementation is included.
