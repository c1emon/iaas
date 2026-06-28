## 1. Cloud-init import and behavior mapping

- [ ] 1.1 Switch to the implementation branch for `reorganize-pve-cloud-init-packages` before editing code.
- [ ] 1.2 Map current tests and code that import symbols from `scripts.pve_inventory.cloud_init`.
- [ ] 1.3 Group current cloud-init helpers by responsibility: model/constants, rendering/config loading, manifest/artifact I/O, SSH upload/verify, CLI parsing/main.
- [ ] 1.4 Decide whether to use an internal helper package name or a file-to-package conversion; pause and update design if command preservation is not straightforward.

## 2. Cloud-init helper package skeleton

- [ ] 2.1 Add the selected internal cloud-init helper package skeleton without removing the stable top-level `cloud_init.py` facade.
- [ ] 2.2 Move cloud-init model/constants such as `CloudInitSnippet` and manifest/timeout constants only if facade re-exports stay straightforward.
- [ ] 2.3 Preserve direct facade imports for stable test-facing symbols from `scripts.pve_inventory.cloud_init`.

## 3. Rendering and artifact internals

- [ ] 3.1 Move generated tfvars loading and cloud-init config extraction helpers into a render/config-focused helper module.
- [ ] 3.2 Move user-data rendering helpers into a render-focused helper module while preserving generated YAML content byte-for-byte where tests assert it.
- [ ] 3.3 Move manifest path/build/write/load helpers into an artifact-focused helper module while preserving manifest schema and fields.
- [ ] 3.4 Keep password hashing and secret handling behavior unchanged; move `secrets.py` only if design is updated to justify it.

## 4. Upload, verify, and facade preservation

- [ ] 4.1 Move SSH timeout, upload command, and verify command helpers into an SSH-focused helper module while preserving command arguments and error handling.
- [ ] 4.2 Keep `parse_args`, `main`, and `python -m scripts.pve_inventory.cloud_init` behavior stable.
- [ ] 4.3 Preserve render/upload/verify subcommand argument semantics and exit behavior.
- [ ] 4.4 Confirm generated snippet content, file names, file IDs, byte counts, hashes, manifest fields, remote paths, and timeout behavior are unchanged.

## 5. Tests and validation

- [ ] 5.1 Update tests that intentionally import moved internals to use new helper package paths while keeping facade import coverage intact.
- [ ] 5.2 Run focused cloud-init tests: `uv run pytest scripts/tests/test_pve_inventory_phase3.py scripts/tests/test_pve_snippet_wrapper.py`.
- [ ] 5.3 Run PVE inventory regression tests that cover generated outputs and validation.
- [ ] 5.4 Run `uv run pytest scripts/tests`.
- [ ] 5.5 Run `make check` and confirm default validation remains offline-safe.
- [ ] 5.6 Run `openspec validate reorganize-pve-cloud-init-packages`.
