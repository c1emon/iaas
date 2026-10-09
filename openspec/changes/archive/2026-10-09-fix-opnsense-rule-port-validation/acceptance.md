# Local acceptance

- OPNsense Python/Ansible regressions and local TLS/proxy integration: **847 passed**, 5 expected warnings for synthetic self-signed HTTPS (123.74s).
- Changed reader/port/writer/mapping tests: 162 passed in the focused rerun.
- Pyright: 0 errors; scoped Ruff, YAML lint, Ansible lint and diff check passed. Import contracts: 4 kept, 0 broken.
- `make check-runtime-contracts`: 2 Python capability tests plus Go launcher integration passed.
- OpenSpec strict validation passed.

Covered: single numeric/string/singleton port, explicit range, port alias, incompatible alias type, non-contiguous and adjacent multi-selector lists, comma strings, bounds, descending/malformed ranges, whole-batch rejection before any provider call, tampered declaration refusal before writes, both Jinja conversions, ordinary/looped no_log failures, mode 0600, field/reason propagation to result and recovery, and stopping before activation after failed save. Invalid native CSV ports remain unrepresentable while reverse-reference evidence is retained.

GitNexus upstream impact warned CRITICAL on admission and HIGH on apply. Change analysis reported CRITICAL; its complete structured response had no partial/truncated marker. Graph navigation is not proof of safety (dynamic Ansible/provider dispatch and broad graph matches need source/test corroboration). No graph counts were changed in AGENTS.md. New files were reviewed directly.

Evidence is local software and synthetic provider/server coverage only. No device writes, release, reconciliation or replay occurred. Alias syntax is checked without external facts in an isolated document; supplied declaration/context facts and planning's effective live dependency checks establish port type.

The original API validation field was not retained, so the conversion defect is not established as the only failure cause. Execution `73a28250-7c43-4a30-813b-1dd4634a65c5` was reported as partially written and pending_reconciliation; that live status was not independently rechecked here. Reconcile first, then generate and approve a new plan. Do not replay the old apply.

## Global critical-output follow-up

Inspected 128 no_log occurrences plus exception/capture/output boundaries across OPNsense, PVE, K3s, switch and VM baseline, using representative paths at the shared callback/runtime/launcher boundaries. Added safe failed/unreachable task summaries, protected warning counts, known assertion gate reasons, sanitized API fields/reasons and HTTP/authentication/permission/timeout summaries. Runtime JSON and launcher stderr preserve these diagnostics and failed phases, including warnings from successful runs. Ordinary raw errors/warnings retain their existing behavior; protected unknown text remains private with a failure code and capture location.

- Repository Python/Ansible run: 2373 passed, 3 skipped; 4 failures exposed an unwanted null phase-status field. Removed that field and reran all relevant private-CA, runtime-dispatch/recovery and public-output tests: **89 passed**, including all 4 previously failing cases. The full suite was not repeated after this localized correction.
- Latest new public-diagnostic/callback tests: 15 passed. Local OPNsense TLS/proxy integration: **23 passed**, 5 expected self-signed HTTPS warnings.
- Go launcher unit tests and `make check-runtime-contracts` passed. Scoped Ruff, Pyright (0 errors), YAML/Ansible lint, import contracts (4 kept), strict OpenSpec validation and diff checks passed.
- Refreshed GitNexus and inspected complete structured change analysis: 37 changed symbols, 321 affected symbols, CRITICAL risk; no partial/truncated marker. Shared runtime paths were verified directly and with tests. No AGENTS.md counts changed, publication, device write or apply replay occurred.

This establishes local software behavior and synthetic-server coverage, not live infrastructure qualification or publication of every arbitrary backend error string.

## Commit grouping

- `3b33d9d`: OPNsense port admission/provider mapping and safe API/task diagnostic primitives, with grouped tests.
- `ea005e6`: runtime JSON and launcher critical-output propagation, with matching catalog and regression tests.
- Documentation and OpenSpec acceptance are committed separately after strict validation. Each code group received staged GitNexus analysis (CRITICAL, no partial/truncated marker) and staged diff checks. Commits are local; no push was requested.

## Archive validation

Archived on 2026-10-09 and promoted deltas into the three main specs. All three pass standard spec validation. Strict spec validation reports exactly the same pre-existing long-requirement warnings as before archive (25 workflow, 1 filter-rule, 2 launcher); no new issues were introduced. Repository-wide strict validation reports 32 passed and 20 failed specs, so it is not recorded as a clean global check. The implementation change passed strict validation before archive. Publication of this branch and a PR targeting main were subsequently authorized; merging or replaying apply is outside this step.
