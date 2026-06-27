## Context

This change is the first roadmap item from `docs/review-remediation-roadmap.md` after the global code review. It intentionally covers only Phase 1 stop-the-bleeding work plus the minimum acceptance checks needed to prove behavior remains bounded.

```text
                docs/review-remediation-roadmap.md
                              │
                              ▼
              fix-review-p1-remediations
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   guest sudo model     repository hygiene   validation UX
   ops vs verifier      dead script/docs     CLI/static_ip
```

The change should not become the cloud-init determinism project. The later `make-cloud-init-snippet-verification-deterministic` change will own manifest/checksum/exact-upload behavior.

## Goals / Non-Goals

**Goals:**

- Make the `ops` guest user suitable for non-interactive automation and align cloud-init rendering with guest verification.
- Preserve `sudo -n true` as a hard check for reachable guests.
- Retire the broken legacy SKS8300 smoke script rather than leaving a known-unusable repository script.
- Bring documented PVE node facts back in line with inventory facts.
- Ensure runtime state/cache artifacts are not tracked and that repository checks/docs make that expectation visible.
- Give validation CLIs stable, traceback-free error output for normal validation failures.
- Make invalid static IP values fail with validation context instead of raw parser context.

**Non-Goals:**

- Do not implement cloud-init snippet checksum verification, manifests, exact file upload, or SSH subprocess timeout changes.
- Do not redesign guest user management beyond the `ops` sudo alignment.
- Do not strengthen VM hostname/group/tag schemas in this change.
- Do not add services Markdown escaping.
- Do not add OPNsense schema validation.
- Do not introduce a shared `scripts/common/` package.
- Do not consolidate PVE API clients or runtime config parsing.
- Do not delete ignored local runtime artifacts automatically.

## Decisions

### Treat `ops` as the automation user

The first-version guest verification already uses `ops` and checks non-interactive sudo. This change should resolve the mismatch by making `ops` the explicit automation account:

```text
clemon  -> human admin user, password-protected sudo
ops     -> automation user, non-interactive sudo for Ansible/verification
root    -> no direct SSH login by default
```

Implementation may use an explicit `NOPASSWD` sudo rule for `ops` that is sufficient for Ansible become and `sudo -n true`. A narrower allowlist can be considered later, but it must not break the existing guest verification contract.

The important boundary is that this applies to the VM guest automation user, not to PVE node SSH users or PVE API identities.

### Retire the legacy SKS8300 smoke script instead of fixing it here

`scripts/sks8300_smoke.py` imports a module path that no longer exists in the repository. Recreating that smoke matrix would require choosing current switch collection APIs and is unrelated to P1 remediation.

This change should remove or archive the entrypoint and ensure no current Makefile, docs, or tests direct operators to run it as a supported command.

### Do not clean local ignored files automatically

The review found local runtime artifacts in the working tree, but ignored local files may be useful to the current operator. This change should not run broad deletion of `.terraform/`, `.venv/`, `.cache/`, `ansible/collections/`, or state backups.

Instead it should establish reviewable hygiene:

```text
tracked forbidden artifact  -> fail / fix source control
ignored local artifact      -> document / leave to operator cleanup
```

At minimum, validation for this change should prove `git ls-files '*.tfstate*'` is empty. If existing ignore rules are incomplete, update them.

### Normalize validation errors at CLI boundaries

Validation failures caused by operator-authored YAML should be normal command failures, not Python tracebacks.

Recommended CLI behavior:

```text
stderr: FAIL validation: <message>
exit:   1
```

Unexpected programming errors may still raise tracebacks during development; this change only catches repository `ValidationError`-style expected validation failures at CLI boundaries.

### Keep static IP handling narrow

Invalid `static_ip` values should be wrapped with field context such as `vms.<name>.static_ip` or equivalent repository-specific context.

This is not the broader VM schema-hardening change. Name, group, tag, DNS, and list element validation belong to `strengthen-pve-and-service-inventory-validation`.

## Risks / Trade-offs

- `NOPASSWD` sudo for `ops` increases guest-side automation privilege. The trade-off is intentional because `ops` is the automation account and guest verification already requires non-interactive sudo. Keep `clemon` password-protected and root SSH disabled.
- A narrow sudo allowlist may break existing Ansible become behavior. Prefer a known-working explicit `ops` rule first; revisit allowlisting only with tests.
- Deleting a legacy script may surprise anyone who used it manually. Mitigate by checking references and noting the retirement in tasks/docs if needed.
- Adding too much hygiene automation could delete local operator state. Keep deletion out of scope.
- Over-expanding validation here could turn this small remediation into the Phase 3 validation project. Keep only static IP error wrapping in scope.

## Acceptance Shape

The implementation should be accepted when:

- `make check` still runs offline.
- Generated outputs are unchanged except for explicitly intended documentation or guest sudo output changes.
- `ops` rendered cloud-init sudo policy and guest verification expectations agree.
- `scripts/sks8300_smoke.py` is no longer a broken supported entrypoint.
- `git ls-files '*.tfstate*'` is empty.
- Validation CLIs return exit code 1 and no traceback for repository validation errors.
- Invalid VM static IP tests produce contextual validation errors.
