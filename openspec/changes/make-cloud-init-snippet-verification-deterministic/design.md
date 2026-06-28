## Context

Phase 2 follows the completed P1 remediation that aligned the `ops` automation user with guest verification. The next reliability gap is the cloud-init snippet lifecycle used by `infra/tofu/pve/Makefile` and `scripts/pve_inventory/cloud_init.py`.

Current shape:

```text
make apply
  ├─ upload-user-data
  │   ├─ render-user-data       # writes local cache
  │   └─ cloud_init upload      # renders again and uploads stdin
  ├─ verify-user-data
  │   ├─ render-user-data       # writes local cache again
  │   └─ cloud_init verify      # renders again but remote verifies only exists/non-empty/YAML
  └─ tofu apply
```

Cloud-init password hashes are generated at runtime with random salt. That is desirable across separate operations, but it means repeated renders within one `make apply` can produce different snippet content. Because the PVE wrapper currently verifies only file presence, non-empty content, and YAML parseability, a stale remote snippet can pass verification even when it differs from the current local user-data artifact.

Desired shape:

```text
make apply
  ├─ render-user-data
  │   ├─ writes exact snippet files
  │   └─ writes manifest.json with sha256 for each snippet
  ├─ upload-user-data
  │   └─ uploads exact files named in manifest
  ├─ verify-user-data
  │   └─ remote wrapper compares stored files to manifest sha256 values
  └─ tofu apply
```

## Goals / Non-Goals

**Goals:**

- Make one render output the source of truth for upload and verify within a single operation.
- Record a local manifest with enough metadata to audit which snippet files were uploaded and what checksum each file should have.
- Make remote verification fail when the stored snippet is stale or differs from the manifest checksum, even if the remote file is valid YAML.
- Keep rendered snippets and manifests ignored and treated as sensitive-adjacent runtime artifacts.
- Add bounded SSH subprocess behavior so upload/verify do not hang indefinitely.
- Preserve the existing audited host-side wrapper boundary for PVE node file writes.

**Non-Goals:**

- Do not make cloud-init password hashes deterministic across separate operations.
- Do not commit rendered cloud-init snippets, manifests, password hashes, or checksum manifests.
- Do not change guest user policy, Ansible guest verification semantics, or OpenTofu VM resource structure.
- Do not add cloud-init upload/verify to default offline `make check`.
- Do not introduce a remote backend or change local OpenTofu state ownership.

## Decisions

### Use manifest-driven exact artifacts

The render command should write both snippet files and a manifest under the existing ignored `.cache/pve-cloud-init/user-data/` tree. Upload and verify should consume that manifest and the exact files it names instead of calling the renderer internally.

This keeps the random password hash salt model intact while making the operation lifecycle deterministic:

```text
random salt allowed ──► rendered file fixed ──► sha256 fixed ──► remote comparison exact
```

Alternative considered: seed or fix the password hash salt. Rejected because it weakens the secret model and the roadmap explicitly avoids cross-run password hash determinism.

### Keep manifest local and ignored

The manifest should include non-secret metadata such as schema version, generation timestamp, source tfvars path/checksum, storage ID, snippet file names, VM IDs/names, byte counts, and SHA-256 values. Even without plaintext secrets, it is derived from runtime-rendered sensitive-adjacent files and should remain ignored.

Alternative considered: commit the manifest for review. Rejected because it would create confusing churn from runtime timestamps and password-hash-derived checksums, and it could imply that rendered runtime data is source-controlled.

### Extend the existing PVE wrapper for checksum verification

`infra/pve-node/bin/astra-pve-snippet-upload` is already the audited sudo boundary. It should continue to constrain storage IDs and filenames, and gain checksum verification such as `--verify --sha256 <expected>`.

The wrapper can retain YAML parse validation as an additional sanity check, but checksum mismatch must be the authoritative stale-content failure.

Alternative considered: run `sha256sum` directly over SSH from Python. Rejected because it bypasses the existing constrained wrapper and broadens the remote command surface.

### Keep Makefile targets explicit and online-only

`make render-user-data` remains local. `make upload-user-data` and `make verify-user-data` remain explicit credentialed/online operations and should not become dependencies of root `make check`.

The likely Makefile shape is:

```text
render-user-data   -> render snippets + manifest
upload-user-data   -> require existing manifest, upload exact files
verify-user-data   -> require existing manifest, verify exact checksums
apply              -> render -> upload -> verify -> backup -> tofu apply
```

### Add timeouts at the Python SSH boundary

Upload and verify SSH subprocesses should use a bounded timeout and convert timeout failures into repository validation/operator errors. The timeout should be configurable enough for slow NFS or SSH environments but have a safe default.

## Risks / Trade-offs

- **Manifest drift** → If inventory or secrets change after render but before upload, the manifest can be stale. Mitigation: upload/verify should describe the manifest source and tasks should test exact-file behavior; operators can rerun render intentionally.
- **Sensitive cache retention** → Rendered snippets and manifests remain in `.cache`. Mitigation: docs already treat `.cache/pve-cloud-init/user-data/` as sensitive; update docs to mention manifest/checksum files.
- **Remote tooling variance** → PVE nodes may lack a specific checksum binary. Mitigation: implement checksum verification using conservative shell tools available on Debian/PVE or Python if already required for YAML validation.
- **NFS/root-squash behavior** → Existing wrapper mode handling should remain unchanged. Mitigation: checksum verification reads the final stored file after install rather than assuming ownership/mode details.
- **False confidence from YAML check** → YAML validity alone is insufficient. Mitigation: checksum mismatch must fail regardless of YAML validity.

## Migration Plan

1. Add manifest/checksum support behind the existing `render`, `upload`, and `verify` command names.
2. Update Makefile targets so `apply` renders once and upload/verify reuse the generated manifest.
3. Update docs to describe the manifest and exact-artifact workflow.
4. Validate with unit tests and offline wrapper tests; live testing can manually upload, verify, alter a remote snippet, and confirm verification failure.

Rollback is straightforward: restore the previous render-on-upload/verify behavior and wrapper verify semantics. No persistent schema or committed generated artifact migration is required.

## Open Questions

- Should upload also pass the expected SHA-256 to the wrapper immediately after install, so upload fails if the stored file does not match what was sent?
- Should manifest generation include a source inventory checksum in addition to `generated.auto.tfvars.json` checksum?
- What default SSH timeout is appropriate for this homelab environment: 20s, 30s, or configurable via Makefile/env?
