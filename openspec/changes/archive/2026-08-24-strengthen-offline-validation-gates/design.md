## Context

The root offline gate currently checks generated outputs, tests, inventory YAML, and OpenTofu. Pyright is configured but not project-managed; Ansible lint is installed but not gated; strict OpenSpec validation is manual. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**

- Make each additional validation concern callable through a named repository target.
- Keep `make check` safe on disconnected infrastructure networks and in cloud CI.
- Make CI install exactly the project-owned toolchain needed by the expanded gate.

**Non-Goals:**

- Do not include live Ansible guest verification, PVE preflight/health, firewall/switch access, or any mutation workflow.
- Do not introduce a broad static-analysis platform or change runtime behavior.

## Decisions

### Keep the gate layered but aggregate it in `make check`

Dedicated `typecheck`, `ansible-lint`, and `openspec-validate` targets retain fast local diagnosis. The aggregate target invokes all of them, so passing the advertised offline gate proves the complete baseline.

### Pin Node-based OpenSpec with pnpm and Python Pyright with uv

OpenSpec is a Node CLI and belongs in committed pnpm development dependencies; Pyright belongs in the Python development dependency group. CI installs both lockfiles before invoking only repository-owned commands.

### Lint repository playbooks, not live inventory execution

Ansible lint runs against maintained playbooks and roles. It must not connect to an inventory, require credentials, or execute guest verification.

## Risks / Trade-offs

- Existing lint violations will initially fail the gate → fix them in this change instead of weakening the lint scope.
- Two dependency managers increase setup time → each owns its native toolchain and lockfile, avoiding ad-hoc global tools.
- OpenTofu provider validation may vary by host platform → retain the existing validation target and report provider execution failures as environment defects rather than bypassing formatting or static checks.

## Migration Plan

1. Add pinned tool dependencies and named validation targets.
2. Resolve all repository Ansible lint failures.
3. Update CI and documentation to use the locked toolchains and aggregate gate.
4. Verify the aggregate gate without runtime secrets or infrastructure access.
