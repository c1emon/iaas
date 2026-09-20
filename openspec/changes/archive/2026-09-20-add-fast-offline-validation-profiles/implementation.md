## Implementation

- Registered strict `fast` and `integration` pytest markers in `pyproject.toml`.
- Marked five bounded pure offline modules as `fast`:
  `test_common_primitives.py`, `test_opnsense_conversion.py`,
  `test_opnsense_alias_graph.py`, `test_opnsense_dnat.py`, and
  `test_k3s_operations.py`.
- Marked three local-tool test modules as `integration`:
  `test_import_contracts.py`, `test_pve_make_workflow.py`, and
  `tests/ansible/test_opnsense_recovery.py`.
- Added `test-fast`, `test-integration`, `test-opnsense`, `test-pve`,
  `test-k3s`, and `check-fast` Make targets. The existing `test` and `check`
  targets retain full collection and the CI aggregate gate remains unchanged.
- Documented the bounded collections, offline boundaries, and measurement
  limits in `docs/development-validation.md`.

Validation evidence for this stage:

- `make test-fast`: 161 passed, 1180 deselected in 0.56s; no environment or
  credential inputs were required.
- `make test-integration`: 18 passed, 1323 deselected in 13.11s; the selected
  tests use local tools and inert/synthetic inputs.
- Collection-only: 1341 full items, 161 fast items, and 18 integration items.
  The previous full baseline recorded 1339 executed items in 190.41s (1337
  passed and 2 failures caused by the then-current lint-imports dependency
  order; the two targeted reruns passed after that order was corrected). The
  current collection does not remove those tests. The timings are scope and
  cache observations only; they do not claim a comparable speedup or establish
  a fixed performance gate.
- A temporary unknown-marker probe failed collection under strict marker mode
  (exit 2), and the empty `fast and integration` selection returned pytest's
  no-tests exit code 5. The probe file was removed afterward.
- `openspec validate add-fast-offline-validation-profiles --strict` and
  `git diff --check` passed. CI workflows still invoke the full `make check`
  gate. Parallel xdist support is deferred because no isolated benefit was
  measured; no image build, device access, or credentialed operation is part of
  this change.
