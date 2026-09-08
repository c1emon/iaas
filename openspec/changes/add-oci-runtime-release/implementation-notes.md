# Implementation evidence

Implementation started on `feat/add-oci-runtime-release` from `61c7d4e`, with a
clean worktree and explicit user authorization to create the branch.

GitNexus refreshed on 2026-09-08. Makefile impact is UNKNOWN; direct source
inspection identifies CI, operator commands and entrypoint tests as callers.
`resolve_ssh_timeout` reports HIGH (four upstream symbols/four process summaries);
the affected path is cloud-init upload/verify through `run_ssh_snippet_command`.
The warning was reported before editing. `upload_snippets`, `verify_snippets`,
`run_ssh_checks`, cloud-init `parse_args`, and both service/foundation
`build_markdown` targets report LOW. Shared CLI dispatch accounts for indirect
renderer results. No host operations were performed.

First implementation phase: explicit Make environment/output paths, resource
exports, output overlap checks, generic document source descriptions, SSH timeout
naming, helper/bootstrap/sudoers migration and OPNsense source selection.
The host prerequisite is documented in `docs/operations/pve-helper-cutover.md`.
No host cutover occurred. The remaining directory/UID container qualification
and operator example migration will be completed with the packaged entrypoint;
tasks 1.2–1.5 remain open until that combined check is complete.

Initial checks: 13 Ansible entrypoint tests and eight directory tests passed.
Python group initially returned 352 passed/three failed because generated source
descriptions had changed. Regenerated the two affected documents; the 26 service
and foundation tests then passed.

Subsequent whole pytest run: 492 passed, five failed on old OPNsense path
assertions/missing explicit environment selection. Updated those test callers;
the complete 22-test OPNsense group then passed. The external-directory group
passes nine tests, including readonly inputs, a working directory outside the
checkout, spaces in directory names, current UID output ownership, stale output
and input-overlap rejection. PVE helper/cloud-init/preflight group: 107 passed.
Type checking: zero errors. Ansible lint: 31 files passed after YAML line wrapping.
OpenSpec strict validation passed. GitNexus change analysis reports eight affected
flows and HIGH risk, localized to renderers and cloud-init as described above;
the MCP result has no partial/truncated flag. No image/publication evidence yet.

## Container phase in progress

Credential boundary clarification and matching operator docs were committed as
`ae4f45e`, after the initial runtime-path phase `37e0b35`. The runtime group keeps
the existing Paramiko 5.0.0 lock and selects ansible-core 2.21.3. A representative
credential-input test passes without an op executable or service token; it also
rejects missing API inputs and an overly readable secret file. This is synthetic
input handling, not live 1Password qualification.

The initial amd64 build runs on wsx in `/tmp/iaas-oci-release.8caiyG`, with image
tag `iaas-runtime:oci-release-test` and log `build.log`. Only reusable source was
transferred; no environment or credential material. The first context predates
the local NOTICE/uv-license additions and Apple metadata exclusion, so it is not
the final acceptance build. Check its existing process/log before rebuilding.
At the latest observation it had installed runtime Python dependencies and was
installing Collections. No container acceptance or release task is complete.
Remove task-owned remote workspace and image after the tests; preserve shared
Docker resources. Source references for pinned download/redistribution choices:
https://docs.astral.sh/uv/guides/integration/docker/,
https://opentofu.org/docs/intro/install/standalone/,
https://docs.hashicorp.com/packer/install,
https://www.hashicorp.com/blog/hashicorp-adopts-business-source-license.

The first and layered builds completed. The synthetic offline container smoke
passed generation/freshness, K3s render, UID and negative path cases. One
source-only Makefile comment rebuild hit both uv and Collection install caches;
the first final RootFS layer remained identical (`dependency-before.txt` and
`dependency-after.txt` on the task workspace). The temporary source edit was
restored; the cache-test image is task-owned and still requires cleanup.

Further resource inspection found and repaired an overly broad pruning rule
that removed Ansible's executable `plugins/test` package. Actual OPNsense plugin
import then identified missing runtime httpx; added the existing locked 0.28.1
version. This rebuild is currently session 69503, log `build-httpx.log`; inspect
that handle before restarting. The latest local pruning also removes upstream
Collection OpenSpec material and base-system READMEs identified by the standard
Docker layer check; this final pruning edit is not yet in that running build.
The current local smoke script adds Ansible resource imports, shipped role syntax
checks and optional external-root backend-disabled OpenTofu init/validate with
lockfile preservation. Its final combined acceptance remains pending.

The httpx build subsequently passed complete smoke, including packaged Ansible
roles/plugins and the external OpenTofu module root (provider 0.111.1), unchanged
provider lock and no state creation. Final pruning layer inspection passed after
fixing the inspector to distinguish `/usr/bin/test` from a test directory.
The later Collection closure audit found community.general's indirect
`community.library_inventory_filtering_v1` dependency; pinned it to 1.1.5. The
updated build/smoke/layer check is session 12531, log `build-closure.log`; it is
still active at the last observation. Local smoke now asserts every Collection
dependency constraint against its shipped manifest version.

Checkout aggregate validation passed on 2026-09-08: 512 tests, type checking,
Ansible lint, generated freshness, YAML, OpenTofu fmt/init/validate and OPNsense
validation. Two initially failing Make-path tests were repaired to isolate
inherited Make flags/directory variables. Gitleaks scanned 154 commits and
reported no leaks. These are software-only results. Release event and registry
substitute tests: 13 passed; release workflow is drafted, not yet published or
accepted against GitHub. Documentation explicitly retains this limitation.

## Container phase acceptance

Session 12531 completed successfully: the final pinned Collection closure,
synthetic offline smoke, packaged Ansible resources, credential input checks,
external OpenTofu init/validate and layer inspection all passed. This build used
the repository-owned `build.sh`. Local Docker manifest-list digest is
`sha256:ed73619a7b34aaa623be63d54a4b3cb93e835968d6fe3ebf361bad9c6cfa3f62`;
it is a test build, not a GHCR publication reference. The remote workspace and
two task-owned image tags still await final cleanup. Runtime dependency and
source layers are separate, with source-only cache reuse demonstrated earlier.
Release workflow configuration and registry substitutes now have 14 passing
tests, but actual GitHub/GHCR delivery remains unverified.


## Release workflow and documentation acceptance

The release event, registry substitute and workflow contract tests pass (14);
combined with directory-boundary tests, the focused gate reports 23 passed.
The tested image was saved and loaded on wsx; its image ID remained identical
and the temporary transfer archive was removed. This verifies local artifact
continuity, not a GitHub Actions run. Operator docs and the delivery decision
now describe caller-owned credentials, explicit paths, reusable dependency
layers, the release workflow, visibility and retry handling consistently.
OpenSpec strict validation and whitespace checks pass. Task 5.3 remains open:
no actual Release, GHCR digest or anonymous public pull evidence exists yet.

GitNexus change analysis reports medium risk, limited to three new release CLI
flows (event preparation, command execution and image-label verification); all
are covered by the focused release tests. The result is neither partial nor
truncated. The wsx task workspace and both task-owned image tags were removed
after validation; shared Docker services and caches were preserved.

## First Release attempt and build-context repair

The authorized `v0.1.0-rc.1` Release targets
`3c697f5a4f73af8334f27e61cc0e540be344c720`. Release workflow
https://github.com/c1emon/iaas/actions/runs/34184974368 passed source validation,
the aggregate gate, secret scan, image build and runtime smoke, but failed layer
inspection: checkout tests had created 17 empty `__pycache__` directories.
The Docker ignore patterns excluded directory contents rather than directories
themselves. No image was pushed; public consumption remains unverified.

The repair excludes cache/test/example/provider directories themselves and adds
explicit Python compilation before PR image builds. The existing image-layer
check then exercises the previously missing post-Python-execution context.
Dependency definitions and the published Release tag remain unchanged.

A minimal Docker build on wsx using the exact repaired ignore file retained a
source file while excluding both populated bytecode caches and empty excluded
directories. Its temporary container, image tag and directory were removed.
The 14 release contract tests, OpenSpec strict validation and whitespace checks
pass. GitNexus reports low change risk with no partial/truncated result; the
Make target is not indexed, so its two CI callers were checked directly.

## Final publication acceptance — 2026-09-08

The user authorized `v0.1.0-rc.2` from
`42fd9c82511de2d9a646e02e6f7bd7148b688f5a`. The Release is
https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.2 and the successful workflow is
https://github.com/c1emon/iaas/actions/runs/34185770926 (attempt 2).

Published digest:
`ghcr.io/c1emon/iaas-runtime@sha256:9feb560f05a059e37c7bfc0a6f7042bfe6d6a6510cf8edb86f498bd2c03cb5c8`.
Build, aggregate checks, synthetic runtime smoke, layer inspection, tested-image
save/load identity and publication succeeded in attempt 1. The anonymous job
initially failed because the package was private. The owner set it public and
reran the failed job; anonymous digest pull and help invocation then succeeded,
without rebuilding or republishing. The local CLI could read Actions results
but lacked permission to request a rerun, so that action was performed by the
owner in GitHub.

An independent wsx check used a fresh empty DOCKER_CONFIG, anonymously pulled
the exact digest and ran its help with networking disabled and a read-only root.
OCI source/revision/version labels matched the authorized release. The temporary
configuration and task-downloaded image were removed, with no container left.
No infrastructure deployment, host helper cutover, Forgejo qualification or
repository visibility change was performed. All tasks in this change are now
supported by software and publication evidence; unrelated delivery phases remain
open. The published tag stays on the tested source commit; subsequent documentation
commits only record acceptance.
