## Why

The repository root `README.md` is currently a project status summary plus selected validation guidance. It does not yet serve as a complete operator manual for people who need to understand repository capabilities, source-of-truth files, module entrypoints, runtime parameters, secret injection, safety boundaries, and where detailed design information lives.

Detailed operational and design information is also spread across root README content, module README files, and `docs/`. Readers need clearer layering: the root README should answer "how do I use this repository safely?", while `docs/` and module README files should hold deeper design, runbook, and module-specific details.

This change is documentation-only. It should reorganize documentation entrypoints for humans without changing automation behavior.

## What Changes

- Rework the root `README.md` into an operator manual for the repository.
- Expand `docs/README.md` into a documentation index that points to architecture, runbooks, decisions, generated references, roadmap, and module-specific guides.
- Clarify the documentation layering between root README, `docs/`, and module README files.
- Document repository capabilities, source-of-truth files, generated outputs, safety classes, common workflows, runtime parameters, and secret-injection conventions at the appropriate level.
- Keep detailed design/rationale/runbook content in `docs/` or module README files rather than overloading the root README.
- Link to `docs/roadmap.md` for current roadmap status after the roadmap consolidation change provides that entrypoint.

## Capabilities

### New Capabilities

- `operator-documentation-entrypoints`: Defines the expected human-facing documentation entrypoints and layering for repository operation.

### Modified Capabilities

- None.

## Impact

- Planned repository areas:
  - root `README.md`
  - `docs/README.md`
  - links or short status notes in existing module README files only if needed for navigation consistency
- Explicit non-impact:
  - No application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior changes.
  - No roadmap item implementation.
  - No OpenSpec archive/status cleanup.
  - No large documentation file moves unless explicitly scoped by a later change.
