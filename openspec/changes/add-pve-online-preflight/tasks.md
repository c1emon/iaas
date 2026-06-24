## 1. Discovery and Integration Boundaries

- [x] 1.1 Inventory current `pve-check-pve`, PVE Makefile targets, env templates, wrapper scripts, and docs that mention online PVE checks.
- [x] 1.2 Confirm which PVE API endpoints or client library calls can read nodes, bridges, storage, VM/template records, and PCI mappings without mutation.
- [x] 1.3 Decide whether the first implementation uses direct HTTP calls, `httpx`, provider-adjacent helpers, or another existing Python dependency for the PVE API client.
- [x] 1.4 Confirm SSH adjunct commands are read-only and limited to wrapper presence/help/sudo checks.

## 2. Preflight Model and Result Semantics

- [x] 2.1 Add a preflight expected-resource derivation path that reuses `validate_cluster`, `validate_vms`, and `build_model`.
- [x] 2.2 Derive required nodes from VM nodes and template nodes referenced by declared VMs.
- [x] 2.3 Derive required bridges, storage roles/datastores, templates, VMIDs, cloud-init snippet storage, and used passthrough mappings from the validated model.
- [x] 2.4 Treat used resources as blocking requirements and declared-but-unused placeholder resources as warnings.
- [x] 2.5 Define pass/warn/fail/skip result objects with actionable messages and no secret disclosure.
- [x] 2.6 Define exit behavior: non-zero on failures, zero on pass/warn/skip without failures.

## 3. API-First Online Checks

- [x] 3.1 Implement PVE API runtime configuration from `TF_VAR_pve_endpoint`, `TF_VAR_pve_api_username`, `TF_VAR_pve_api_token_id`, `TF_VAR_pve_api_token_secret`, and `TF_VAR_pve_insecure`.
- [x] 3.2 Validate API reachability and token authentication without printing token secrets.
- [x] 3.3 Check required PVE nodes exist and report unused declared nodes as warnings when unavailable.
- [x] 3.4 Check required VM bridges exist on the selected VM nodes.
- [x] 3.5 Check required storage IDs exist and satisfy the expected content roles where PVE exposes that data.
- [x] 3.6 Check required template VMID/name/node records exist and are marked as templates.
- [x] 3.7 Check declared VMIDs are free or match expected repository ownership markers.
- [x] 3.8 Check used PCI passthrough mappings exist and are compatible with the selected VM node where supported by available PVE checks.

## 4. SSH Adjunct Checks

- [x] 4.1 Add optional SSH context handling for `PVE_HOST` and `PVE_SSH_USER` without making SSH required for API checks.
- [x] 4.2 Check `astra-pve-snippet-upload` presence/help or verify behavior through read-only passwordless sudo when SSH context is provided.
- [x] 4.3 Check `astra-pve-template-build` presence/help through read-only passwordless sudo when SSH context is provided.
- [x] 4.4 Report SSH adjunct checks as skipped or non-blocking when SSH context is absent, unless an explicit require-SSH mode is implemented.
- [x] 4.5 Ensure SSH adjunct checks do not upload snippets, modify files, change sudoers, create VMs, or mutate PVE configuration.

## 5. Command Surface and Documentation

- [x] 5.1 Add canonical root `make pve-preflight` delegating to the PVE module preflight target.
- [x] 5.2 Add `infra/tofu/pve` preflight target invoking the repository-owned preflight implementation.
- [x] 5.3 Decide whether `pve-check-pve` becomes a compatibility alias to `pve-preflight` or remains as a legacy smoke check, and document the choice.
- [x] 5.4 Document API-first invocation using `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-preflight`.
- [x] 5.5 Document optional SSH adjunct invocation with `PVE_HOST` and `PVE_SSH_USER`.
- [x] 5.6 Update validation docs to keep `pve-preflight` outside `make check` and cloud CI.

## 6. Tests and Fixtures

- [x] 6.1 Add unit tests for expected-resource derivation from current inventory fixtures.
- [x] 6.2 Add tests for pass/warn/fail/skip result aggregation and exit semantics.
- [x] 6.3 Add fake PVE API response tests for API auth, nodes, bridges, storage, templates, VMID ownership, and PCI mapping readiness.
- [x] 6.4 Add tests ensuring token secrets and resolved runtime credentials are not printed in reports or errors.
- [x] 6.5 Add fake SSH tests for wrapper presence, wrapper missing, SSH context absent, and require-SSH behavior if implemented.
- [x] 6.6 Add regression tests proving `make check` and GitHub Actions do not invoke `pve-preflight`.

## 7. Validation

- [x] 7.1 Run `make check` locally.
- [x] 7.2 Run preflight unit tests locally.
- [x] 7.3 Run `make secret-scan` locally.
- [x] 7.4 Run `openspec validate add-pve-online-preflight`.
- [x] 7.5 If PVE runtime credentials are available, run API-first `make pve-preflight` locally and record the result.
- [x] 7.6 If SSH context is available, run `make pve-preflight` with `PVE_HOST` and `PVE_SSH_USER` and record SSH adjunct results.
- [ ] 7.7 Inspect CI after pushing to confirm only offline validation runs in GitHub Actions.
