# Repair-first design review — 2026-09-10

Scope: expanded proposal, feature design, repair-plan.md, thirteen delta specifications,
dependency review and implementation tasks. This is design acceptance only. No code
repair, dependency installation, device qualification or release is completed by these
artifacts. All implementation tasks remain unchecked.

## Prerequisite repair decisions

The repository audit and three independent agent reviews establish R01–R16 in
[repair-plan.md](repair-plan.md). The map connects each finding to a capability,
implementation task and representative acceptance case. Tasks 0.1–0.14 and gate 0.15
must finish before the dependency refresh (stage 1) or features (stages 2–5).

- Retain Make/Python/Ansible/OpenTofu responsibilities; repair ordering and artifact
  continuity without introducing a workflow engine.
- Preserve ordinary no-op behavior while adding explicit force-reload recovery to
  fixed OPNsense targets. Check mode and failed CRUD never activate.
- Separate K3s lifecycle admission from shared observation probes; stage artifacts
  before service interruption and verify actual versions and node identity.
- Keep neutral foundation schema version 2 optional storage facts and explicit legacy
  schema version 1 compatibility; never rewrite caller configuration implicitly.
- Treat optional saved plans as deferred integration work, not an authorization bug.
  Type=notify limits the startup-race claim; bounded polling is a modest repair detail.
- Use realistic synthetic failures and the actual entrypoints for software evidence.
  The earlier 56 passing tests demonstrate coverage gaps, not completed repairs.

## Earlier feature-design findings retained

| Finding | Evidence | Resolution |
| --- | --- | --- |
| Arbitrary positive refresh decimals were not preserved | Pinned Collection `build_updatefreq`: `0.01 -> 0.0`, `0.15 -> 0.1`, `0.5 -> 0.5`, reproduced locally | At least 0.1 days, at most one fractional digit, finite unchanged numeric conversion; reject rounding before API access |
| Absent groups could not be deleted with absent members | The initial local-reference scenario applied to every group | Surviving desired graph validates references; live graph orders deletions; obsolete absent-group content has syntax checks only |
| Existing live definitions could cause false cycles or block a released dependency | A group can switch to a new member and remove its former member in one request | Overlay desired updates/removals with external definitions; create new dependencies, update groups, then delete old members |
| Complete external-consumer preflight was not established | Pinned AliasUtil findReferences accepts an IP; AliasController deletion has the actual whereUsed guard | Do not promise exhaustive preflight; retain server refusal and never remove outside consumers |
| Missing rule correlation could turn into false zero matches | Rule-filtered queries need identity mapping; IP queries do not | Required selector capability missing is unsupported/null counts; optional metadata can be unavailable |
| API failures can be indistinguishable from empty observations | Alias table API defaults backend errors to an empty list; query_states has a current=0 fallback | Unknown observation/null counts where indistinguishable; detectable invalid fallback is error; no unsupported stub acceptance |
| Single-host and OCI availability were underspecified | Existing OCI entrypoint only permits opnsense-validate; zero Ansible hosts skip device tasks | Exact host variables, controller-local scope admission, operation allowlist and image entrypoint checks |
| Dependency-stage smoke was not executable runtime proof | Current build uses a final image containing Makefile/entrypoint after dependency stages | Build and smoke the final image with candidate dependencies; preserve later source-only cache reuse |
| Alias type change is not a safe ordinary update | Pinned Collection refuses in-place type change | Fail in preflight; no implicit delete/recreate |


## Requirement coverage

| Requirement / boundary | Authoritative artifacts | Implementation acceptance |
| --- | --- | --- |
| Repair-first sequencing | Proposal, repair plan, OCI delivery delta | Tasks 0.1–0.15 before any stage 1–5 work |
| PVE entrypoints, ordered phases and current artifacts | OCI delivery and PVE foundation deltas | Tasks 0.1–0.3 |
| K3s lifecycle, truthful observations and handoff | K3s operations and platform handoff deltas | Tasks 0.4–0.7 |
| Network activation, admission and usable reports | Alias/gateway/VIP/filter-rule/validation, export and switch deltas | Tasks 0.8–0.10 |
| Recovery dependencies, neutral policy and bounded health | Foundation and K3s deltas | Tasks 0.11–0.13 |
| Reproducible main gate and image layering | OCI delivery delta and dependency review | Task 0.14, repair gate 0.15, tasks 1.1–1.2 |
| URL table and network groups | Alias and mutation-validation deltas; feature design | Tasks 3.1–3.4 |
| Alias observation, rule logs and states | Read-only diagnostics delta | Tasks 4.1–4.4, all kinds implemented |
| Application chooses integration and credentials | Proposal ownership boundaries and both design documents | Generic fixtures; no op runtime integration, ciop or device writes |
| Documentation and actual software evidence | Feature design and repair plan | Repair documentation at 0.15; feature documentation at 5.1–5.3; live adoption remains separate |

## Final semantic review

- Made standalone K3s preflight mode explicit and bound deploy/upgrade to their own
  admission modes. Fresh hosts, artifact-only re-entry, current and prior versions,
  and foreign state now have defined outcomes.
- Limited legacy foundation compatibility to field layout and storage scope. New
  dependency and probe-safety checks apply to both schema versions. Defined neutral
  storage fields, strict dependency order and the optional inventory-relative CA path.
- Named the protected diagnostic output parameter and rejected input overlap and
  implicit detail opt-in. Required observations masked as empty by upstream APIs
  now explicitly return unsupported/nonzero with null counts.
- Included affected operator documentation, help and migration notes in the repair
  gate so their completion cannot be deferred until feature acceptance.

## Review outcome

The expanded artifacts cover both audit rounds and preserve the original feature
scope. The repair phase corrects confirmed defects and includes small directly related
reliability changes; saved-plan integration and live/DR qualification remain deferred.
Strict OpenSpec validation passed for this design update. Cross-artifact checks found
30 distinct unchecked implementation tasks in contiguous stages, all 16 audit items
mapped, thirteen delta specifications and valid local document links. Modified
requirements retain their existing scenario identities for safe archive replacement.
Implementation evidence must be recorded on the approved implementation branch before
any checkbox or phase gate is marked complete.
