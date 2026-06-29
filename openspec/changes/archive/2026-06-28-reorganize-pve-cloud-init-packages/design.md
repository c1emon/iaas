## Context

`scripts/pve_inventory/cloud_init.py` is still a single large module that owns several responsibilities:

```text
cloud_init.py
├── CLI parsing for render/upload/verify
├── generated tfvars and cloud-init config loading
├── user-data rendering and password hashing integration
├── manifest creation, persistence, and loading
├── SSH upload command construction/execution
├── remote verification command construction/execution
└── top-level main/exit behavior
```

This is intentionally more sensitive than the inventory-core and health splits because tests and workflows may import callable helpers directly, and upload/verify behavior touches explicit operator-controlled remote systems. The refactor should preserve the stable top-level module while moving internals into a responsibility-oriented package only after import surfaces are mapped.

## Goals / Non-Goals

**Goals:**

- Group cloud-init internals by responsibility while preserving `scripts.pve_inventory.cloud_init` as the stable command and import facade.
- Preserve generated user-data content, manifest schema/contents, upload command semantics, verify command semantics, and CLI exit behavior.
- Preserve existing test-facing helper names by re-exporting them from the top-level facade when tests intentionally import them.
- Keep secret/password hashing behavior unchanged and avoid leaking secret values in errors or generated metadata.

**Non-Goals:**

- Do not change cloud-init template content, manifest schema version, snippet file naming, or remote storage path semantics.
- Do not change inventory generation, online preflight, health, or PVE API runtime behavior.
- Do not add new PVE mutation operations or widen default offline validation.
- Do not move `cloud_init.py` itself unless a documented command-preservation approach is added first.

## Decisions

### Decision: Keep top-level `cloud_init.py` as the stable facade

Target shape:

```text
scripts/pve_inventory/
├── cloud_init.py                 stable CLI/import facade
└── cloud_init_helpers/           or cloud_init/ if command facade can stay stable
    ├── __init__.py
    ├── model.py                  CloudInitSnippet/constants
    ├── render.py                 tfvars parsing, user-data rendering
    ├── artifacts.py              manifest path/build/write/load
    ├── ssh.py                    upload/verify command execution
    └── cli.py                    optional parser/main helpers if facade remains thin
```

Rationale: `python -m scripts.pve_inventory.cloud_init` and direct imports from `scripts.pve_inventory.cloud_init` are the stable surfaces. Internals can move, but the module path should remain usable.

Alternative considered: convert `cloud_init.py` into a `cloud_init/` package with `__main__.py`. Rejected as the first approach because a file-to-package conversion can be riskier for imports and should only be chosen if it cleanly preserves module execution and direct imports.

### Decision: Split render/artifact/SSH responsibilities before CLI internals

Start by moving pure-ish internals:

- render/model helpers: snippet dataclass, tfvars loading, user-data rendering
- artifact helpers: manifest path/build/write/load
- SSH helpers: timeout resolution, upload and verify command execution

Leave `parse_args`, `main`, and facade exports in `cloud_init.py` until internals are stable.

Rationale: this keeps the command surface boring while reducing the size and responsibility mix of the implementation.

### Decision: Treat `secrets.py` movement as optional and conservative

Keep `scripts.pve_inventory.secrets` top-level unless implementation shows that moving it into a cloud-init package does not break imports or misclassify future secret helpers.

Rationale: password hashing is currently cloud-init-specific, but top-level `secrets.py` may be less disruptive than moving security-sensitive helpers during the first cloud-init split.

## Risks / Trade-offs

- File-to-package name collision → Prefer internal helper package names or keep `cloud_init.py` as a facade unless a safe conversion plan is explicit.
- Generated content drift → Assert rendered snippet content and manifest fields in existing tests before/after the move.
- Upload/verify command drift → Preserve command argument order, timeout behavior, remote paths, and error handling.
- Secret handling drift → Keep password hashing behavior unchanged and avoid adding logging of resolved secret values.

## Migration Plan

1. Map all tests and code importing `scripts.pve_inventory.cloud_init` symbols.
2. Add internal cloud-init helper package skeleton without moving the top-level facade.
3. Move model/render helpers, then artifact helpers, then SSH upload/verify helpers, updating facade re-exports as each group moves.
4. Keep `parse_args`, `main`, and command entry behavior stable; optionally move parser helpers only after command tests pass.
5. Update tests that intentionally target internals to new paths while preserving facade import coverage.
6. Run cloud-init focused tests, full scripts tests, `make check`, and OpenSpec validation.

Rollback is straightforward: restore moved helpers into `cloud_init.py` and revert imports. No generated artifacts or remote systems are changed by the refactor itself unless an operator explicitly runs upload/verify commands.

## Open Questions

- Should the internal package be named `cloud_init_helpers/` to avoid file/package conflicts, or should the change convert `cloud_init.py` into a package with `__main__.py`?
- Should `secrets.py` move into the cloud-init package or remain top-level as a conservative shared helper?
- Which cloud-init helper functions are intentionally public test-facing exports versus internal-only implementation details?
