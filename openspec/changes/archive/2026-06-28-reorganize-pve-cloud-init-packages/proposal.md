## Why

`scripts/pve_inventory/cloud_init.py` combines cloud-init rendering, artifact manifest handling, SSH upload/verification, and CLI orchestration in one large command module. Splitting the internals into a `cloud_init/` package will improve maintainability while keeping the existing cloud-init command facade and generated snippet behavior stable.

## What Changes

- Introduce internal cloud-init helper modules grouped by responsibility, such as rendering/artifact I/O, SSH upload/verify behavior, and CLI orchestration helpers.
- Preserve the stable `scripts.pve_inventory.cloud_init` command-facing module path and test-facing exports.
- Preserve cloud-init snippet content, manifest format, upload behavior, verification behavior, and CLI exit semantics.
- Keep password hashing and secret handling behavior unchanged; move `secrets.py` only if the design proves it belongs inside a cloud-init package without widening import churn.
- Do not change offline inventory generation, online preflight, PVE health, or PVE API runtime behavior.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `pve-inventory-package-organization`: Clarify that cloud-init helper internals may be grouped into a responsibility-oriented package while preserving the stable command facade and output behavior.

## Impact

- Affected code:
  - `scripts/pve_inventory/cloud_init.py` and any new internal cloud-init helper modules.
  - Tests that import cloud-init render/upload/verify helpers or assert generated artifact contents.
  - Imports of `scripts.pve_inventory.secrets` if password hashing helpers are moved or re-exported.
- Operational impact:
  - No PVE mutation behavior beyond the existing explicit cloud-init upload command.
  - No changes to generated snippet content or manifest semantics.
  - Existing Makefile/module entrypoints remain stable.
- Non-goals:
  - Changing cloud-init template content or upload target paths.
  - Changing PVE inventory model/render/validation packages.
  - Changing online preflight, health, or PVE API runtime behavior.
