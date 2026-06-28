## Context

The repository now has two explicit online PVE checks:

- `pve-preflight` answers whether declared resources are ready for plan/apply-like workflows.
- `pve-health` answers whether the current PVE cluster/runtime state is healthy for routine review and future maintenance prechecks.

The command semantics are intentionally different, but their plumbing overlaps. `scripts/pve_inventory/preflight_api.py` currently owns a urllib-based GET client, local redaction, and `RuntimeError` handling. `scripts/pve_inventory/health.py` uses `scripts/pve_inventory/pve_api/`, a proxmoxer-backed read-only facade with typed safe exceptions and redaction helpers. Runtime configuration is also split between `preflight_config.py`, `health.py`, and `pve_api/client.py`.

This change should consolidate the shared API/runtime adapter boundary without widening online behavior, adding mutations, or collapsing preflight and health into one command.

Current shape:

```text
                 ┌──────────────────────┐
                 │ inventory YAML model │
                 └──────────┬───────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌─────────────────┐                     ┌─────────────────┐
│ pve-preflight   │                     │ pve-health      │
│ apply-ready?    │                     │ healthy-now?    │
└────────┬────────┘                     └────────┬────────┘
         │                                       │
         ▼                                       ▼
┌─────────────────────┐                 ┌──────────────────────┐
│ preflight_api.py    │                 │ pve_api/client.py    │
│ urllib GET client   │                 │ proxmoxer facade     │
│ RuntimeError errors │                 │ typed PveApiError    │
└─────────────────────┘                 └──────────────────────┘
         ▲                                       ▲
         │                                       │
┌─────────────────────┐                 ┌──────────────────────┐
│ preflight_config.py │                 │ health.py local cfg  │
│ RuntimeConfig       │                 │ HealthApiRuntimeConfig│
└─────────────────────┘                 └──────────────────────┘
```

Desired boundary shape:

```text
                 ┌──────────────────────┐
                 │ pve_api/runtime.py   │
                 │ shared env parsing   │
                 └──────────┬───────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌─────────────────┐                     ┌─────────────────┐
│ pve-preflight   │                     │ pve-health      │
│ readiness logic │                     │ health logic    │
└────────┬────────┘                     └────────┬────────┘
         │                                       │
         └───────────────┬───────────────────────┘
                         ▼
              ┌────────────────────┐
              │ PveReadOnlyApi     │
              │ protocol / facade  │
              └─────────┬──────────┘
                        │
        ┌───────────────┴────────────────┐
        ▼                                ▼
┌─────────────────────┐          ┌──────────────────────┐
│ urllib adapter      │          │ proxmoxer adapter    │
│ transitional if kept│          │ current health layer │
└─────────────────────┘          └──────────────────────┘
```

## Goals / Non-Goals

**Goals:**

- Define a shared read-only PVE API protocol/facade shape for repository-owned online PVE checks.
- Centralize PVE API runtime environment parsing for endpoint, token credentials, TLS verification, and optional SSH adjunct context.
- Standardize safe PVE API exceptions and secret redaction across preflight and health checks.
- Let `pve-preflight` and `pve-health` use the same fake-client/protocol shape in tests.
- Preserve existing preflight readiness semantics, health semantics, CLI entrypoints, reports, and exit behavior.
- Keep online checks explicit and outside default offline validation and cloud CI.

**Non-Goals:**

- Do not merge `pve-preflight` and `pve-health` commands.
- Do not add PVE mutation methods or remediation operations.
- Do not move PVE API code into `scripts/common`; it remains PVE-domain code.
- Do not require immediate deletion of the urllib backend if a transitional adapter reduces behavior risk.
- Do not change capacity thresholds, health warning semantics, preflight readiness rules, or generated inventory behavior.
- Do not include rolling maintenance, node reboot, VM migration, update, start/stop, snippet upload, or OpenTofu apply behavior.

## Decisions

### Decision: Consolidate the boundary before consolidating the backend

Implement a shared facade/protocol and shared runtime/error contracts first. A first pass may leave both urllib and proxmoxer backends present if both implement the same read-only facade.

Rationale: current risk is not merely duplicated HTTP code; it is that callers see different runtime parsing, exception types, redaction, and fake-client contracts. Unifying those contracts yields most of the maintainability benefit without forcing a backend migration that might subtly change endpoint behavior.

Alternative considered: immediately delete the urllib preflight client and route everything through proxmoxer. Rejected for the first pass because preflight currently has route-level tests around exact endpoint paths and query strings, especially PCI mapping and VMID ownership checks. That migration can be a later small change once the shared facade is covered.

### Decision: Define named read-only methods, not a generic `get_json(path)` shared API

The shared API boundary should expose named read-only facts such as `nodes()`, `node_network(node)`, `node_storage(node)`, `cluster_vm_resources()`, `vm_config(node, vmid)`, `pci_mappings()`, `ha_status()`, and `ceph_status()`.

Rationale: a generic `get_json(path)` would keep raw PVE endpoint knowledge spread through preflight and health logic. Named methods keep endpoint traversal inside adapters while leaving PASS/WARN/FAIL/SKIP semantics in the domain check modules.

Alternative considered: expose both named methods and `get_json(path)`. Rejected unless a temporary migration shim is unavoidable, because generic raw access makes it easy for future checks to bypass the facade.

### Decision: Runtime parsing belongs under `pve_api`, not in each command

Add or evolve a runtime module that owns parsing of:

- `TF_VAR_pve_endpoint`
- `TF_VAR_pve_api_username`
- `TF_VAR_pve_api_token_id`
- `TF_VAR_pve_api_token_secret`
- `TF_VAR_pve_insecure`
- optional `PVE_HOST` / `PVE_SSH_USER` for SSH adjunct checks

It should return an API-only config for health and an online-context config for preflight when SSH adjunct context is needed.

Rationale: health and preflight already use the same credential convention. Keeping parsing in one place prevents boolean parsing, missing-variable messages, and future secret handling from drifting.

### Decision: Safe error and redaction are adapter contracts

Adapters should raise repository-owned `PveApiError` subclasses with operator-safe messages. Authentication, unavailable, and not-configured conditions should remain distinguishable for health and preflight semantics. Redaction should be shared and tested with token secrets.

Rationale: check modules should decide whether an unavailable optional subsystem is `SKIP`, `WARN`, or `FAIL`, but they should not need to know urllib/proxmoxer exception shapes or how to scrub token values from exception text.

### Decision: Preserve command semantics and reporting

`pve-preflight` remains apply-readiness oriented and may still run optional SSH adjunct checks. `pve-health` remains current cluster/runtime health oriented and does not perform readiness bootstrapping or maintenance actions. Both continue to use `CheckResult`-style pass/warn/fail/skip reporting.

Rationale: the commands answer different operator questions. Shared plumbing must not collapse their domain semantics.

## Risks / Trade-offs

- Backend migration changes PVE endpoint behavior → First unify facade/runtime/error contracts and keep a transitional urllib adapter if needed.
- Protocol grows too broad → Only add methods needed by existing preflight and health checks; do not add mutation or speculative endpoints.
- Error normalization hides useful context → Preserve status codes and safe body/status messages while redacting secrets.
- Optional HA/Ceph/PCI endpoints behave differently across PVE versions → Keep existing skip/warn/fail semantics and retain fake response variants in tests.
- Runtime config refactor breaks online commands → Add focused tests for environment parsing, missing variables, boolean parsing, and secret redaction.
- Fake tests become tied to one backend → Prefer protocol fake tests for check semantics, with small adapter-specific tests for urllib/proxmoxer error mapping.

## Migration Plan

1. Add shared runtime config and read-only API protocol/facade definitions under `scripts/pve_inventory/pve_api/`.
2. Normalize PVE API errors/redaction and expose them from the package.
3. Extend the proxmoxer-backed facade to cover the named facts needed by both health and preflight.
4. If needed, wrap the existing urllib client as a transitional implementation of the same read-only facade.
5. Update `health.py` and `preflight.py` to use shared runtime parsing and the shared facade shape.
6. Keep the existing check modules' domain semantics and result IDs stable unless a test reveals an intentional improvement that should be explicitly documented.
7. Run offline tests and online-guard checks; if runtime credentials are available, smoke-test explicit `make pve-preflight` and `make pve-health` manually.

Rollback is straightforward: revert the adapter/runtime refactor while keeping the existing preflight and health command implementations. No infrastructure state or data migration is involved.

## Open Questions

- Should the first implementation keep a transitional urllib adapter, or migrate preflight directly to the proxmoxer facade once protocol-level tests are in place?
- Should `preflight_api.py` remain as the readiness-check semantics module, or should it be renamed once transport concerns move into `pve_api/`?
- Should the completed `add-pve-cluster-health-check` change be archived before this change is implemented so the health capability is present in main specs?
