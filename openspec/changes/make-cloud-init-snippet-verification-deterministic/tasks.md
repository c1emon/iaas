## 1. Scope Confirmation

- [ ] 1.1 Confirm determinism is scoped to a single render/upload/verify operation, not to cross-operation password hash stability.
- [ ] 1.2 Confirm rendered snippets and manifest/checksum files remain ignored local runtime artifacts and must not be committed.
- [ ] 1.3 Confirm cloud-init upload/verify remain explicit online operations and do not enter root `make check`.

## 2. Manifest and Exact Artifact Rendering

- [ ] 2.1 Add a manifest representation for rendered cloud-init snippets, including schema version, generation metadata, source tfvars checksum, storage ID, snippet file names, VM identity, file IDs, byte counts, and SHA-256 checksums.
- [ ] 2.2 Update `scripts/pve_inventory/cloud_init.py render` to write snippet files and manifest together under the configured output directory.
- [ ] 2.3 Ensure manifest checksums are computed from the exact bytes written to disk.
- [ ] 2.4 Add or update tests proving render writes snippets plus manifest with expected file IDs, byte counts, and SHA-256 values.

## 3. Upload and Verify from Existing Artifacts

- [ ] 3.1 Update upload behavior so it reads the existing manifest and snippet files instead of implicitly re-rendering user-data.
- [ ] 3.2 Update verify behavior so it reads the existing manifest and verifies the remote snippets against manifest checksums instead of implicitly re-rendering user-data.
- [ ] 3.3 Ensure upload fails clearly if the manifest is missing, references a missing snippet file, or the local file checksum does not match the manifest.
- [ ] 3.4 Ensure verify reports the failing snippet filename or VM identity without printing plaintext secrets, password hashes, private keys, or token material.
- [ ] 3.5 Add tests proving upload/verify consume exact local files and do not call the renderer again after manifest creation.

## 4. PVE Wrapper Checksum Verification

- [ ] 4.1 Extend `infra/pve-node/bin/astra-pve-snippet-upload` to accept an expected SHA-256 checksum for verify mode.
- [ ] 4.2 Preserve existing storage ID, filename, path, mode, and YAML validation guardrails.
- [ ] 4.3 Ensure wrapper verify succeeds for matching content and fails for checksum mismatch without mutating the remote snippet.
- [ ] 4.4 Add offline wrapper tests for matching checksum, mismatched checksum, missing file, and invalid arguments where practical.

## 5. SSH Timeout and Operator Errors

- [ ] 5.1 Add bounded timeouts to cloud-init upload and verify SSH subprocesses.
- [ ] 5.2 Make timeout failures operator-readable and free of runtime secret values.
- [ ] 5.3 Keep unexpected programming errors debuggable rather than catching them too broadly.
- [ ] 5.4 Add tests for timeout handling using a fake subprocess runner or equivalent seam.

## 6. Makefile and Documentation

- [ ] 6.1 Update `infra/tofu/pve/Makefile` so `apply` renders once, then upload and verify consume the rendered manifest/artifacts.
- [ ] 6.2 Preserve explicit `render-user-data`, `upload-user-data`, and `verify-user-data` targets with clear required environment variables.
- [ ] 6.3 Update `infra/tofu/pve/README.md` to document the manifest-driven cloud-init flow and checksum verification behavior.
- [ ] 6.4 Update `docs/pve-state-cache-secrets.md` to identify cloud-init manifests/checksums as ignored sensitive-adjacent runtime artifacts.

## 7. Validation

- [ ] 7.1 Run focused PVE inventory/cloud-init tests.
- [ ] 7.2 Run wrapper-related tests or shell checks.
- [ ] 7.3 Run `make check` locally.
- [ ] 7.4 Run `openspec validate make-cloud-init-snippet-verification-deterministic`.
- [ ] 7.5 Inspect generated output diffs and confirm no committed files contain rendered snippets, password hashes, manifest data, or runtime secrets.
- [ ] 7.6 When implemented and archived, update `docs/review-remediation-roadmap.md` Phase 2 completion status.
