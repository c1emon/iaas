## Why

The current PVE cloud-init upload and verify flow can render user-data multiple times during a single apply, while password hashes include random salt and the remote verifier only checks that snippets exist and contain valid YAML. This means `make apply` cannot prove that the snippet on the PVE node is the exact artifact rendered for the current operation.

This change makes the runtime cloud-init artifact lifecycle deterministic within one operation: render once, record checksums, upload exact files, and verify remote content by checksum before OpenTofu applies VM changes.

## What Changes

- Render cloud-init user-data snippets into local ignored artifacts once per operation and treat those files as the source of truth for upload and verify.
- Generate a local manifest that records snippet filenames, VM identity, storage/file IDs, byte counts, and SHA-256 checksums for the rendered files.
- Change upload and verify flows so they consume existing rendered files and manifest entries instead of implicitly re-rendering user-data.
- Extend the audited PVE host-side snippet wrapper to verify an expected SHA-256 checksum for a stored snippet.
- Preserve runtime password hash generation and random salt behavior; do not make password hashes deterministic across separate operations.
- Add SSH subprocess timeouts and operator-readable failures for cloud-init upload/verify commands.
- Add offline tests for manifest/checksum generation, exact-file upload behavior, checksum mismatch detection, stale remote snippet verification failure, and timeout handling where practical.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pve-automation-foundation`: Require runtime cloud-init snippets to be rendered once into local artifacts, uploaded from those exact artifacts, and verified against remote checksums before apply.
- `pve-state-and-secret-operations`: Clarify that cloud-init manifests/checksums are ignored runtime artifacts adjacent to rendered snippets and must not be committed.

## Impact

- Affected code:
  - `scripts/pve_inventory/cloud_init.py`
  - `scripts/pve_inventory/secrets.py` only if a narrow hook is needed to make single-render tests reliable; do not fix salt globally.
  - `infra/pve-node/bin/astra-pve-snippet-upload`
  - `infra/tofu/pve/Makefile`
  - `scripts/tests/test_pve_inventory_phase3.py` or a focused new cloud-init test module
- Affected docs/specs:
  - `infra/tofu/pve/README.md`
  - `docs/pve-state-cache-secrets.md`
  - `docs/review-remediation-roadmap.md` when the change is completed
  - `openspec/specs/pve-automation-foundation/spec.md`
  - `openspec/specs/pve-state-and-secret-operations/spec.md`
- Operational impact:
  - Operators should render cloud-init artifacts once and then upload/verify those artifacts by checksum.
  - A stale or manually altered remote snippet should fail verification even if it is syntactically valid YAML.
  - The local manifest and rendered snippets remain ignored, sensitive-adjacent runtime files.
- Non-goals:
  - Do not fix cloud-init password salt across separate operations.
  - Do not commit rendered snippets or manifests.
  - Do not change guest user policy, OpenTofu VM resource structure, or guest verification playbooks.
  - Do not add online PVE mutation to `make check`.
