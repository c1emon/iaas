# Implementation evidence

## PVE runtime repairs (0.1–0.3)

- `uv run pytest -q tests/python/test_pve_make_workflow.py tests/python/test_pve_snippet_wrapper.py tests/python/test_pve_inventory_phase3.py`: 109 passed (2026-09-10).
- Real Make recipes run outside the checkout with inherited `MAKEFLAGS=-j8` and inert command substitutes; plan/apply check freshness first, apply orders render/upload/verify, and destroy finds recursive backup targets.
- Upload/verify reject missing or mismatched current tfvars before SSH; existing matching manifest/checksum cases still pass.
- Failed PVE storage resolution exits before creating a directory or writing a snippet; no guessed destination remains.
- This is local software evidence, not live PVE deployment qualification. Remaining stage 0 repairs and its final offline/image gate are still pending.

## K3s observed identity repairs (0.7 and part of 0.6)

- Handoff: 20 tests passed across `test_platform_handoff_tls.py`, `test_platform_handoff_playbook.py`, and `test_platform_handoff.py`. Disposable local X.509 certificates confirm DNS/IPv4/IPv6 SAN selection and wrong-identity/wrong-CA rejection. Connection formatting follows [OpenSSL s_client](https://docs.openssl.org/3.0/man1/openssl-s_client/); authoritative guest CA and Make's same-scope verification remain in place.
- Preflight: 34 tests passed across `test_k3s_first_boot.py`, `test_k3s_preflight.py`, and `test_k3s_template_whitespace.py`. Actual Ansible fact-building tasks parse capability bits and exact address/interface pairs; zero bits, address prefixes and wrong interfaces cannot satisfy the expected observation.
- `ansible-lint` passed for the preflight role and handoff playbook (5 files). These are local synthetic observations and certificate checks; no appliance or cluster was contacted.
- Task 0.6 remains open: upgrade drift and exact post-upgrade version/readiness checks are still pending. Tasks 0.4–0.5 are also pending.

## OPNsense admission and activation recovery (0.8–0.9)

- `uv run pytest -q tests/python/test_opnsense_validation.py`: 30 passed. Current Collection primitive bounds are enforced before credentials/writes; a bad second gateway rejects the batch. Priority/data length zero and representative upper-bound failures are covered.
- `uv run pytest -q tests/ansible/test_opnsense_recovery.py`: 8 passed. Actual activation blocks run with inert command substitutes for all four managed resource kinds, covering no-op, failed reload then explicit no-change retry, check mode, invalid string flags and a preceding partial-CRUD failure. Direct Ansible destination inversion checks agree with Python cases.
- Ansible lint passed for all four managed playbooks plus imported credential preflight (5 files). No appliance API was contacted; saved/active behavior on real appliances is not qualified here.

## Foundation contracts, probes and generic artifact paths (0.11–0.13)

- Foundation inventory/probe and acquisition tests: 51 passed across `test_foundation_inventory.py`, `test_foundation_probes.py`, and `test_k3s_mirror_acquisition.py`. Cases include schema 1 compatibility, schema 2 with no storage, optional VLAN/node classes, dependency cycles/closure/order, relative CA paths, real loopback HTTPS trust/identity failures, all six DNS types, malformed packets and compression loops. Test servers are shut down and temporary certificate files are pytest-owned.
- K3s model, acquisition admission and template regressions: 89 passed before the three additional exact binary version cases were added; those three are included in the 51-test run above. No artifact host was contacted: real Ansible assertion/version tasks use local executable substitutes. Artifact URL path conventions are caller-owned, while pinned checksum acquisition and exact reported version remain required.
- Ansible lint passed for the acquisition role (3 files); pyright reports 0 errors (existing missing `scripts` include-path notice remains). Generic foundation fixture and generated documentation now use schema 2 with unambiguous external-host/service names.
- These results do not complete K3s lifecycle admission/staging repairs or the stage 0 final synthetic offline/image gate. No live infrastructure mutation or release publication occurred.

## K3s lifecycle admission and upgrade repairs (0.4–0.6)

- Standalone preflight requires an explicit mode; actual deployment/upgrade imports select and enforce their operation's mode. Read-only installation probes use current generated unit/configuration, binary checksum/version, systemd source and datastore facts. Unknown ownership, missing mutation-scope hosts and unavailable required observations cannot admit deployment/upgrade.
- Upgrade refreshes all supplied version observations before snapshot/mutation, stages checksum- and version-verified artifacts before stopping, and refuses replacement on stop failure. Real systemd failures are no longer masked. Bounded post-node checks require exact identity, role, version and established Ready/CNI-bootstrap semantics; shared verification runs over the whole scope at completion. Failures retain the staged file and report manual recovery without downgrade/datastore rollback.
- `test_k3s_upgrade_staging.py`: 5 local real-task cases passed (download/checksum/version/stop failure and successful activation), using file transport and a service command substitute. Active files/services remain unchanged in the failure cases.
- Preflight/upgrade/state/staging grouping: 47 passed; final stop/start failure handling recheck: 12 passed. Actual server/agent template-and-probe execution in disposable roots: 2 passed. K3s group run: 266 passed, 3 outdated acquisition assertions failed; updated acquisition file rerun: 7 passed. The prior URL/version policy tests now correspond to actual version verification and never try external downloads.
- Relevant Ansible lint passed for 27 files; strict OpenSpec validation and pyright passed. These are software-only tests and substitutes, not a real K3s upgrade rehearsal. The stage 0 final offline/image gate remains pending.

## Operator reports and export isolation (0.10)

- Switch previews expose object change type and field names without raw commands or configuration values; optional per-target detail uses the existing runtime path guard and private directory/file permissions. OPNsense exports are isolated by inventory identity and attributed in each JSON artifact.
- Representative real local Ansible tasks verify two independent firewall exports, sanitized switch console output, opt-in detail and 0700/0600 permissions. Four report tests and eleven existing XikeOS migration tests passed; affected Ansible lint passed (9 files). No device was contacted.

## Shipped CI baseline and initial Stage 0 gate (0.14)

- Main CI now pins OpenTofu 1.12.6 and uv 0.12.9 and installs the same explicit Collection closure as the shipped image with `--no-deps`. Candidate dependency updates have not started. Existing dependency-before-source Docker layers are unchanged.
- `make check` against the synthetic environment passed: 614 tests, YAML validation, pyright (0 errors), Ansible lint (31 files), OpenTofu formatting/init/validation, generated-output checks and OPNsense offline admission. PVE/K3s syntax checks and strict OpenSpec validation passed. This is software-only evidence.
- Final-image build/smoke remains outstanding: this Mac has no Docker CLI; the authorized wsx connection failed because the SSH agent could not sign (communication with agent failed). No remote resource was created. Task 0.15 and stages 1–5 remain unchecked until the final image is tested.

## Final Stage 0 image acceptance (0.15)

- After wsx SSH agent access recovered, built the final linux/amd64 image from commit `77e8b68` using an isolated task builder. Loaded the cached result explicitly because the docker-container builder does not load images by default.
- The existing `automation/runtime/smoke.py --tofu` passed against that image: offline generation/check, shipped plugin loading and Collection dependency closure, K3s render, caller UID, rejected missing/unsafe/stale inputs, and external synthetic OpenTofu init/validate. No infrastructure plan/apply or live appliance operation was run.
- `automation/runtime/inspect_image.py` passed: excluded runtime contents absent and required OS/tool notices retained. Together with the 614-test offline gate and strict validation above, this completes Stage 0 on the shipped baseline. The temporary build workspace and isolated builder remain task-owned for the following dependency build and will be removed at final cleanup.

## Reviewed dependency refresh (1.1–1.2)

- Upgraded Ansible to 14.4.0 and exact core to 2.21.4. Selective `uv lock` changed only these two package versions; both Collection manifests now align community.general 13.4.0 and ansible.netcommon 8.6.2. Other reviewed dependencies and Docker tool/system pins are unchanged.
- Candidate `make check` passed all 614 tests and the complete synthetic offline gate. Actual pinned Collection helpers also passed representative XikeOS VLAN planning/idempotency and OPNsense frequency/reference checks.
- Rebuilt and loaded the candidate final linux/amd64 image on wsx. Its core reports 2.21.4; existing final-image smoke (including external synthetic OpenTofu init/validate) and image-layer inspection both passed. This is software-only compatibility evidence, with no live appliance qualification or image publication. The isolated builder is retained for source-layer reuse and final task cleanup.

## Pinned interfaces and alias lifecycle (2.1–3.4)

- Recorded controller/backend/ACL contracts in `upstream-interface-review.md` against core 26.1.11 and the installed Collection. Synthetic diagnostic response shapes and generic alias/Gateway/PBR examples are under `tests/fixtures/opnsense-capabilities/`; no live appliance was queried.
- Added URL tables with lossless decimal-string frequency, provider name syntax and network groups. Shared offline validation rejects local reference errors; read-only live planning overlays desired definitions, checks reachable external dependencies/type continuity and orders updates before live-graph removals. Native Collection batches retain the server deletion guard and activate only after all successful changes (or explicit recovery). Check mode only reads and plans.
- 90 focused tests passed, including real Ansible task sequencing with a stateful inert API substitute: create dependencies first, ordinary no-op, forced activation, check mode, pre-write refusal, partial failure and server consumer refusal. Syntax and strict OpenSpec checks passed; pyright reported zero errors. No claim of URL fetch success or data-plane qualification is made.

## Bounded read-only diagnostics (4.1–4.4; 5.1)

- Implemented all three adapters and the Make/direct-Ansible/OCI operation entrypoints. Target selection is validated while resolving the controller admission play, before credentials; a separate request/path admission step precedes device access. Details remain opt-in and protected, while console output contains only the versioned summary.
- Fixed read operations use standard HTTP timeouts, per-response/cumulative byte limits and bounded pagination. Required selector/correlation fields govern acceptance; optional metadata is independently marked unavailable. Backend-empty ambiguity yields unsupported/null counts; detectable invalid pages yield errors. No mutation operation is accepted.
- 40 Python contract/adapter tests and 21 real entrypoint/shared-transport tests passed. The latter use a local synthetic HTTP server for Make and Ansible, including path spaces, exact/zero/wildcard target rejection, protected detail output, nonzero errors, HTTP failures and response bounds. A controlled timeout substitute checks timeout/TLS/redirect settings. Ansible syntax/lint passed; type checking reported zero errors. Operator examples, permissions and limitations are documented. Final aggregate/source-image acceptance remains task 5.2–5.3.

## Final software acceptance and cleanup (5.2–5.3)

- Final `make check` against the synthetic environment passed: 727 tests, YAML validation, pyright (zero errors), generated-output checks, OpenTofu formatting/init/validation and OPNsense offline admission. Fixed the new nested-Make test's inherited `MAKEFLAGS`/path overrides; a targeted reproduction and full gate rerun passed. The initial lint run found local global-Collection shadowing; rerunning `make ansible-lint` with a disposable `ANSIBLE_HOME` used project-pinned Collections and passed all 33 files with zero failures or warnings.
- Built the final linux/amd64 runtime from `bb5f018` on wsx. Transfer-mode differences initially invalidated dependency cache; after matching the prior build's 0644 dependency-input modes, Python installation, Collection installation, pruning and the final dependency filesystem all reported `CACHED`, while repository source layers rebuilt. No dependency file content or Docker layering changed.
- The updated `automation/runtime/smoke.py --tofu` passed: existing generation, K3s, plugin/Collection closure, caller UID and input-failure checks, plus exact OPNsense filter availability and actual OCI diagnostic request rejection before credentials/API access. Synthetic external OpenTofu init/validate passed. `inspect_image.py` passed its layer-content and license-notice checks. This is software-only evidence, not live OPNsense, PVE, switch, K3s or traffic qualification; no image was published.
- Strict OpenSpec validation and the standard redacted secret scan passed. Final GitNexus change analysis covered eight changed symbols in five files, reported low risk, and returned neither partial nor truncated results. The changed smoke/test helper paths were also checked directly and executed above. Roadmap status is complete pending separate archive.
- Removed the task's wsx builder/cache, all three task image tags and the temporary workspace after retaining concise local build/smoke/inspection logs. Shared Docker resources were not pruned. All change tasks are complete; no PR, push, merge or archive was performed.

## Independent implementation review and corrective acceptance

The independent multi-agent review of `d19adf4` invalidated the preceding final-acceptance conclusion despite the passing tests. It confirmed seven gaps: detail-directory permission traversal, provider validation skipped as success, dictionary-shaped switch previews, mixed-protocol log filtering, missing single-request upgrade timeouts, discarded policy-route observations, and missing partial-CRUD status. Corrections and their actual acceptance evidence are recorded below; the earlier section remains historical evidence only.

- Diagnostics now normalize and independently bound the detail destination before permission changes, exclude provably unrelated rows before requiring unavailable AND-selector fields, and retain available policy-route observations. Nine new regression cases failed on the old implementation and passed after correction; 70 unit/real-local-entrypoint tests passed. Independent cross-review and 11 targeted checks found no remaining diagnostic issue.
- Alias/rule batches explicitly make provider validation failures fatal. Offline URL syntax and rule sequence limits match the pinned provider. Gateway/VIP/rule CRUD failures now report partial saved state and do not activate it. The 96-test focused group passed, including actual Collection parameter/validation code and actual playbook rescue paths. A separate reviewer checked the provider implementation and reran six representative tests successfully.
- Switch summaries consume the actual dictionary results of all four interface resource types while retaining list resources and private-value suppression. Nine kubectl API calls across the upgrade path, snapshot and shared verification use a 15-second request timeout. Forty focused tests passed, including native Collection lifecycle results through the report task and a real local kubectl timeout on an incomplete HTTP response; affected K3s lint passed for 13 files.
- The review also exposed the stale `scripts`/`ansible` type-check paths. The gate now covers current automation source, Ansible code and runtime helpers, excludes installed Collections and resolves the project package explicitly. Minimal type narrowing and an accurate `NoReturn` annotation resolve source errors; two line-local override exceptions document the pinned Ansible abstract stub's incorrect inferred return type. Independent `pyright --verbose` confirmed 84 source files checked with zero errors or warnings. These changes do not suppress source-wide diagnostic categories.
- All three implementation areas received independent cross-review, with no further substantiated findings. The final aggregate gate and rebuilt current-source image results follow below; no historical image is used to qualify the corrective patch.
- Corrective `make check` passed all 746 tests, current-source type checking, YAML/generated-output validation, synthetic OpenTofu init/validate and OPNsense offline admission. Two Ansible `args` warnings persisted after dependency isolation: the linter did not resolve the pinned Collection's `all -> system` action-group defaults for alias read/reload. Verified those defaults in provider metadata and added the same task-local annotation used by existing management tasks; final lint passed 33 files with zero failures or warnings. No runtime credential behavior changed.
- Built the final staged source snapshot as a linux/amd64 runtime on wsx, reusing the dependency layer. The current-image `smoke.py --tofu` and layer inspection both passed, including diagnostic/plugin admission and synthetic external OpenTofu validation. Retained concise local logs, then removed the task builder/cache, image and temporary workspace. No shared Docker prune, image publication or live infrastructure operation was performed.
- Strict OpenSpec validation, the redacted secret scan and complete, nontruncated precommit GitNexus analysis passed. With the seven findings and the actual type-gate coverage gap corrected and independently reviewed, software acceptance is restored; live appliance qualification remains separate.
