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
