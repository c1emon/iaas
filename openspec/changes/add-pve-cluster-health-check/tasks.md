## 1. Scope and Health Semantics

- [ ] 1.1 Confirm `make pve-health` as the canonical command name.
- [ ] 1.2 Define required nodes as nodes hosting declared VMs plus nodes hosting referenced templates.
- [ ] 1.3 Define optional placeholder nodes as declared nodes not currently required.
- [ ] 1.4 Confirm node capacity thresholds: CPU WARN >90%, memory WARN >90%, root disk WARN >90%, root disk FAIL >98%.
- [ ] 1.5 Confirm datastore thresholds: WARN >85%, FAIL >95%.
- [ ] 1.6 Confirm lifecycle-aware VM status semantics for long-lived and ephemeral lab VMs.
- [ ] 1.7 Confirm HA and Ceph unavailable endpoints are skipped rather than failed.

## 2. PVE Health Command Implementation

- [ ] 2.1 Add a dedicated PVE health entrypoint, likely `scripts/pve_inventory/health.py`.
- [ ] 2.2 Reuse the existing read-only PVE API client and result/reporting helpers where practical without merging health into preflight semantics.
- [ ] 2.3 Load and validate `inventory/pve-cluster.yml` and `inventory/vms.yml` to derive required nodes, optional nodes, referenced templates, declared VMs, and required storage roles.
- [ ] 2.4 Implement API reachability and credential checks without printing token secrets or resolved runtime credential values.
- [ ] 2.5 Implement cluster status/quorum checks using read-only PVE API data where available.
- [ ] 2.6 Implement node presence, online/status, CPU, memory, and root disk capacity checks.
- [ ] 2.7 Implement storage presence, active/availability, and usage checks for required datastores.
- [ ] 2.8 Implement referenced template presence and template flag checks.
- [ ] 2.9 Implement declared VM runtime status checks with lifecycle-aware warning semantics.
- [ ] 2.10 Implement HA status checks that skip unavailable/not-configured HA and fail on unhealthy HA resources.
- [ ] 2.11 Implement Ceph health checks that skip unavailable/not-configured Ceph and map HEALTH_OK/WARN/ERR to PASS/WARN/FAIL.

## 3. Command Surface and Documentation

- [ ] 3.1 Add root `make pve-health` delegating to the PVE module health target.
- [ ] 3.2 Add `infra/tofu/pve` health target invoking the repository-owned health command.
- [ ] 3.3 Document invocation with `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-health`.
- [ ] 3.4 Document the distinction between `pve-preflight` apply readiness and `pve-health` current cluster health.
- [ ] 3.5 Document capacity thresholds and lifecycle-aware VM warning behavior.
- [ ] 3.6 Update validation docs to keep `pve-health` outside `make check` and cloud CI.

## 4. Tests and Fixtures

- [ ] 4.1 Add unit tests for deriving health expectations from the validated PVE inventory model.
- [ ] 4.2 Add fake API tests for successful quorum, required/optional node handling, and node threshold warnings/failures.
- [ ] 4.3 Add fake API tests for required datastore missing/inactive and datastore threshold warnings/failures.
- [ ] 4.4 Add fake API tests for referenced template missing or not marked as a template.
- [ ] 4.5 Add fake API tests for long-lived VM missing/stopped warnings and ephemeral lab missing/stopped non-warning behavior.
- [ ] 4.6 Add fake API tests for HA endpoint skip, empty HA skip, and unhealthy HA failure.
- [ ] 4.7 Add fake API tests for Ceph endpoint skip, HEALTH_OK pass, HEALTH_WARN warn, and HEALTH_ERR fail.
- [ ] 4.8 Add tests ensuring runtime secrets are not printed in health reports or errors.
- [ ] 4.9 Add regression tests proving `make check` and GitHub Actions do not invoke `pve-health`.

## 5. Validation

- [ ] 5.1 Run `make check` locally.
- [ ] 5.2 Run the PVE health test subset locally.
- [ ] 5.3 Run `make secret-scan` locally.
- [ ] 5.4 Run `openspec validate add-pve-cluster-health-check`.
- [ ] 5.5 If PVE runtime credentials are available, run `make pve-health` locally and record pass/warn/fail/skip results.
- [ ] 5.6 Inspect CI after pushing to confirm only offline validation runs in GitHub Actions.
