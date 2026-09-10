## 0. Repair existing runtime workflows before feature work

Stage 0 is mandatory. Do not start stages 1–5 until 0.15 passes. Before applying
this change, obtain the implementation-branch choice required by AGENTS.md and
preserve the existing uncommitted work. Design updates do not complete these tasks.

- [x] 0.1 Fix recursive Makefile selection, reject stale generated inputs before plan/apply and serialize render → upload → verify → apply even with inherited parallel MAKEFLAGS; reproduce arbitrary-directory and parallel execution with safe command substitutes (R01–R02).
- [x] 0.2 Bind cloud-init upload/verify to the current explicit tfvars through the existing manifest source hash; reject missing, stale or mismatched input before SSH (R03).
- [x] 0.3 Make snippet storage resolution authoritative and fail before directory creation or writes when it cannot be established; remove guessed-path fallback (R04).
- [ ] 0.4 Implement the explicit standalone preflight mode and operation-selected deploy/upgrade modes using the repair-plan state table and shared read-only facts; reject foreign/ambiguous installation state without rejecting an expected installed cluster (R05).
- [ ] 0.5 Stage and checksum upgrade artifacts before stopping services; preserve serial server-before-agent ordering, safe bounded restart verification and explicit failure recovery without datastore rollback (R06).
- [ ] 0.6 Parse real capability bits and exact IP/interface facts; refresh and compare observed versions before upgrade, and verify exact node identity/version/readiness after each upgraded node and at completion (R07).
- [x] 0.7 Correct handoff DNS/IP TLS verification and IPv6 endpoint formatting while preserving authoritative CA and same-scope K3s verification (R08).
- [x] 0.8 Add explicit opnsense_force_reload recovery for managed alias/gateway/VIP/rule workflows, including no-change retry and check-mode behavior; distinguish saved configuration, activation success and partial failure (R09).
- [x] 0.9 Align Gateway numeric bounds with the pinned Collection and correct destination inversion handling in both validation paths; reject an invalid batch before its first write (R10).
- [ ] 0.10 Emit reviewable sanitized switch plan summaries with optional protected detail output; isolate OPNsense export artifacts by target and include target identity (R11–R12).
- [x] 0.11 Reject recovery self-dependencies, cycles, invalid ordering and an incomplete required startup dependency set; derive deterministic recovery output from validated facts (R13).
- [x] 0.12 Introduce optional application-neutral foundation storage facts with explicit legacy compatibility; remove provider-specific K3s artifact URL special cases while retaining exact version/checksum verification (R14).
- [x] 0.13 Make foundation HTTPS trust explicit, require caller-selected DNS resolvers, support the declared record types and bound DNS parsing including pointer cycles; keep observations redacted and failures classified (R15).
- [ ] 0.14 Align the main CI gate with the currently shipped tool/Collection baseline and add representative real-orchestration regressions for repaired entrypoints and lifecycle states; preserve dependency/source image layering (R16).
- [ ] 0.15 Update affected module manuals/help, generic fixtures and migration guidance; complete focused regressions, affected Ansible syntax/lint, the existing synthetic offline gate, final-image smoke and strict OpenSpec validation. Perform GitNexus change analysis before focused repair commits and record software-only evidence. Only then allow stage 1 dependency refresh and stages 2–5 features.

## 1. Refresh the reviewed execution dependencies

- [ ] 1.1 Upgrade Ansible to 14.4.0 and the runtime core pin to 2.21.4 together; update uv.lock selectively and align community.general 13.4.0/netcommon 8.6.2 in both Collection manifests, retaining the reviewed unchanged dependencies.
- [ ] 1.2 Validate the candidate stack with the existing synthetic offline gate and representative OPNsense/XikeOS checks; rebuild the final runtime image with the updated dependency layer and smoke-test that image, record resolved versions and commit this upgrade separately before feature implementation.

## 2. Confirm interfaces and regression scope

- [ ] 2.1 Inspect the pinned Collection and a documented upstream OPNsense version; record methods, schemas, permissions and bounds for alias loading, log queries, rule correlation and state queries, with representative synthetic response fixtures.
- [ ] 2.2 Confirm existing static-alias, Gateway/PBR, credential and path boundaries; define diagnostic request/result schema and document any upstream capability limits without application-specific defaults.

## 3. Extend alias inputs and lifecycle

- [ ] 3.1 Add type-specific `urltable`/`updatefreq_days` and `networkgroup` validation; preserve existing static aliases, unknown-field rejection and pre-credential offline admission.
- [ ] 3.2 Add local dependency validation and explicit read-only resolution of external references, using desired/live effective graphs and preserving the server in-use deletion guard.
- [ ] 3.3 Apply present aliases in dependency order and removals in reverse order through the pinned Collection; preserve unlisted objects, reload-on-success and honest partial-failure reporting.
- [ ] 3.4 Test representative valid/invalid types, lossless refresh precision, references, cycles, simultaneous group/member deletion, reference-release updates, type-change refusal, external ownership and failure-before-write paths; include Gateway/PBR composition regression without adding application policy.

## 4. Add bounded read-only diagnostics

- [ ] 4.1 Implement shared request validation and the Make/direct-Ansible entrypoints using an exact single-host target, explicit input paths, OCI operation allowlist and caller-owned credentials.
- [ ] 4.2 Implement alias loading, rule log and connection-state adapters with fixed read-only operations, bounded responses, selector-specific required fields and explicit optional metadata/correlation.
- [ ] 4.3 Implement versioned summaries, ok/unsupported/error distinctions including unknown-observation nonzero exits, and the explicit OPNSENSE_DIAGNOSTICS_OUTPUT/direct-playbook path for opt-in protected detail files using existing path-safety helpers.
- [ ] 4.4 Test each diagnostic kind with representative success/empty/truncated, unavailable capability, auth/permission failure, timeout, backend-empty ambiguity, missing required correlation and malformed-response cases; verify no mutation calls, sensitive console output or unsafe file writes.

## 5. Documentation and software acceptance

- [ ] 5.1 Update the OPNsense manual and generic examples for resource fields, dependency ownership, entrypoints, required permissions, diagnostic limits and existing Gateway/PBR use.
- [ ] 5.2 Run focused tests, Ansible syntax/lint and the existing synthetic offline gate; verify runtime entrypoint availability and preserve source/dependency image layering without publishing a new image.
- [ ] 5.3 Validate the change strictly and run complete GitNexus change analysis before implementation commits; record actual software evidence and leave live appliance qualification explicitly separate.
