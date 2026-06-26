## Context

The repository already has an explicit online PVE preflight command. Its purpose is apply readiness: before running OpenTofu plan/apply-like workflows, it checks that declared VM resources are visible and safe to consume.

Cluster health is related but different:

```text
                 ┌──────────────────────────┐
                 │ inventory/pve-cluster.yml │
                 │ inventory/vms.yml         │
                 └─────────────┬────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
       ┌───────────────┐                 ┌──────────────┐
       │ pve-preflight │                 │ pve-health   │
       ├───────────────┤                 ├──────────────┤
       │ Apply-ready?  │                 │ Healthy now? │
       │ VM resources  │                 │ Cluster/run  │
       │ available?    │                 │ state OK?    │
       └───────────────┘                 └──────────────┘
```

`pve-health` should be an explicit online read-only operation used for routine operational review and as a precheck before future rolling maintenance runbooks. It should not run maintenance actions itself.

## Goals / Non-Goals

**Goals:**

- Add canonical root `make pve-health`.
- Run read-only PVE API health checks using the same runtime API token conventions as other explicit PVE online operations.
- Report pass/warn/fail/skip results with a non-zero exit only for blocking failures.
- Check cluster quorum when the API exposes quorum state.
- Check required node online/status facts and optional placeholder node availability.
- Check node CPU, memory, and root disk capacity thresholds.
- Check required storage presence, active state when exposed, and usage thresholds.
- Check referenced template presence and template flag.
- Check declared VM runtime status with lifecycle-aware warning semantics.
- Check HA and Ceph health when available; skip when unavailable or not configured.
- Keep the command outside default offline validation and cloud CI.

**Non-Goals:**

- Do not run OpenTofu plan/apply/destroy or Packer builds.
- Do not upload snippets or modify VM configuration.
- Do not migrate, start, stop, reboot, suspend, or otherwise change VMs.
- Do not enter or leave PVE node maintenance mode.
- Do not update packages, reboot nodes, or perform rolling maintenance.
- Do not mutate Ceph state such as `noout`, pools, OSDs, or monitors.
- Do not send notifications in this change.
- Do not automatically remediate unhealthy conditions.
- Do not require PVE API access in `make check` or cloud CI.

## Decisions

### Add a separate health entrypoint rather than widening preflight

The first implementation should add a dedicated `scripts/pve_inventory/health.py` entrypoint. It may reuse existing helpers such as the GET-only `ProxmoxAPI` client and `CheckResult` reporting functions, but the top-level command should remain distinct from `preflight.py`.

This preserves the semantic boundary:

```text
preflight.py  -> resource readiness for plan/apply-like workflows
health.py     -> current cluster and runtime health view
```

### Define required and optional nodes from inventory usage

Required nodes should be derived from the validated PVE model in the same spirit as preflight:

```text
required nodes = nodes hosting declared VMs + nodes hosting templates referenced by declared VMs
optional nodes = declared nodes not currently required
```

Health semantics:

```text
required node missing/offline    -> FAIL
optional placeholder unavailable -> WARN
```

This keeps the current placeholder-node pattern usable without hiding problems on nodes that actually matter for declared VMs/templates.

### Use explicit capacity thresholds

The first version should include simple built-in thresholds:

| Resource | WARN | FAIL |
| --- | ---: | ---: |
| Node CPU usage | > 90% | none |
| Node memory usage | > 90% | none |
| Node root disk usage | > 90% | > 98% |
| Datastore usage | > 85% | > 95% |

High CPU or memory can be transient, so it should warn rather than fail. Very high root disk or datastore usage can immediately disrupt operations, so critical storage pressure may fail.

Thresholds may become configurable later, but static defaults are sufficient for the first small-scale health command.

### Keep VM runtime checks lifecycle-aware

Declared VM runtime status should inform operators without becoming a duplicate of apply readiness.

Initial semantics:

```text
long_lived VM missing -> WARN
long_lived VM stopped -> WARN
ephemeral_lab missing -> no warning; summarize or skip
ephemeral_lab stopped -> no warning; summarize or pass
```

Templates are stricter because they are shared infrastructure dependencies:

```text
referenced template missing                 -> FAIL
referenced template exists but not template -> FAIL
```

### Treat quorum, HA, and Ceph according to available API facts

Quorum:

```text
cluster status exposes quorate == 1 -> PASS
cluster status exposes quorate == 0 -> FAIL
cluster status lacks quorum data     -> SKIP
```

HA:

```text
HA endpoint unavailable/404       -> SKIP
HA has no resources               -> SKIP
HA resource error/fence/unknown   -> FAIL
```

Ceph:

```text
Ceph endpoint unavailable/404 -> SKIP
HEALTH_OK                    -> PASS
HEALTH_WARN                  -> WARN
HEALTH_ERR                   -> FAIL
```

This keeps single-node or non-Ceph environments from failing only because optional subsystems are absent.

### Keep reporting compatible with existing PVE online checks

`pve-health` should use stable human-readable reporting with severities:

```text
PASS  expected healthy condition
WARN  review-worthy but not blocking
FAIL  blocking unhealthy condition; command exits non-zero
SKIP  optional subsystem/check unavailable or not configured
```

JSON output can be added later if internal CI needs machine-readable health reports. The first version should keep the report human-readable and consistent with `pve-preflight`.

## Risks / Trade-offs

- PVE API response shapes differ by version → Keep parsing defensive and test with fake route variants; skip unknown optional fields rather than failing when no health conclusion can be drawn.
- Capacity thresholds can be environment-specific → Use conservative defaults and leave configurability to a future change if needed.
- Health checks may be mistaken for remediation → Keep command name/reporting/documentation explicit that this is read-only observation.
- Long-lived stopped VMs may be intentionally stopped → Warn rather than fail, giving operators visibility without blocking all health reports.
- HA/Ceph absence is normal in small environments → Skip missing optional subsystem endpoints instead of failing.
