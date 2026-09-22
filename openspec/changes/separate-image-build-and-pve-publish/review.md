# Joint planning review — 2026-09-23

## Scope and status

实施更新：用户已授权双仓实施与分阶段提交，两仓已进入对应实施分支。IaaS 前置 change 已正式归档，task 1.1 完成；后续任务按实际证据更新。以下为此前设计复核记录，不表示当前仍停留在 planning-only；实时实施状态见 [实施记录](../../../docs/operations/image-publish-implementation.md)。

完成双仓planning-only设计后，用户进一步授权修正六项过度门禁；本记录反映修订后的决议，早期严苛规则不再有效。iaas留在feat/adapt-pve-ci-lifecycle，infra-ops留在main；不实现代码/CI、不部署执行器、不操作PVE/S3、不切分支、不提交或归档真实change。所有实施任务保持未勾选。

对应 [infra-ops review](../../../../infra-ops/openspec/changes/integrate-image-build-and-pve-publish/review.md)。权威字段为 [contract](contracts/image-publish-v1.md)，设计选择为 [design](design.md)，未来执行与验收为 [tasks](tasks.md)。

## Independent reviews and resolutions

| Review axis | Finding | Final disposition |
| --- | --- | --- |
| infra_spec: caller boundary and field alignment | CI/executor/credentials/upload/promotion must stay caller-owned; local artifact path must not be rewritten to S3 | Both designs separate ownership; semantic descriptor plus independent object reference; standard transfer completion before handoff and actual disk SHA before PVE writes |
| review_api_feasibility: API/secrets | PVE download-url logs full URL | Single controller-upload path; private locator consumed only by publisher, never sent to PVE |
| API/storage cleanup | upload overwrites same name, delete needs stronger ACL than upload, HTTP temp space differs from destination | Unique name+preexisting refusal+serialization and scoped complete ACL; check local/API capacities, report unobserved temp constraints without mandatory SSH/helper |
| API completion | PVE sets template flag before disk conversion | Require native task success plus independent identity/volume/config verification; unknown response never automatically replayed |
| Image completeness | QEMU backing chain and UEFI efivars can hide external dependencies | Self-contained final qcow2; final offline cleanup; boot disposable copy with fresh UEFI VARS; no build efivars in handoff |
| review_boundaries: action completeness | Recovery requests/read/verify selectors absent | PVE cleanup/retire requests retain admissions; direct local clean uses original task/lock and appends an attempt without another preview |
| Stage proportionality | Uniform plan/apply and build-only boot checks over-constrained local work | Direct image build/test/clean; independent test of existing/external images with disk/policy/runtime binding; read/verify passive; PVE plan/apply remains |
| Recovery identity | Ordinary retire incorrectly required original build recovery_of | Cleanup/recovery requires original association; normal retire binds current template record/admission without inventing history |
| Baseline conflict | Old Packer PVE identity/helper/effects rules survived under added specs | Explicit replacement of old foundation and template requirements; full launcher lifecycle/effects/entrypoint deltas preserve safety semantics |
| Consumer identity | Artifact x86_64 conflicted with canonical VM amd64 | Handoff uses amd64; QEMU-internal mapping is an implementation detail |
| Latest user direction | Legacy record adapters/readers retained only for compatibility | Removed aliases/translators/dual paths; VM consumers directly adopt new records. Only raw historical evidence and safe drain remain |

No unresolved issue from these review scopes remains in the written design. This statement covers planning coherence, not implemented functionality or installed-PVE compatibility.

## Authorized proportionality corrections

1. No default receiving-node space telemetry gate or space helper. Known insufficient capacities still block; unknown temporary-space telemetry is honest diagnostic information, and actual failures use normal recovery.
2. Local build/clean no longer require frozen approval previews, image-build-preview or image-cleanup-request schemas. Task isolation, process termination, resource locks and ownership checks remain.
3. Independent image test produces disk/policy/runtime-bound evidence on a disposable guest without rebuilding or changing the source. PVE publication can explicitly consume those test results; mismatches/conflicts are rejected.
4. No compulsory extra full S3 GET/hash after upload. Standard completion/size/fixed object identity permit handoff as uploaded; content verification is mandatory at consumption before PVE writes. Extra readback is optional site assurance.
5. Verified stopped publication with only known-owned static staging residue succeeds with cleanup warning. Persist terminal result and separate cleanup todo before settling pending; unknown/active/unowned cases still block. Later PVE staging deletion retains new-plan/current-admission checks.
6. Descriptor digest is semantic canonical JSON, with strict schema and duplicate-key rejection. Whitespace/key order do not trigger new plans; semantic fields and actual disk bytes remain bound.

These are scope reductions authorized by the user, not blanket weakening of VM/state/OPNsense protections. Reviewers independently checked the revised boundary and API semantics; the validation results below were rerun for the revised files, including the independent-test evidence consumption rules.

## Validation evidence

- `openspec validate separate-image-build-and-pve-publish --strict`: passed in actual iaas worktree.
- Actual-worktree validation emits an expected INFO that the launcher execution-identity requirement is not yet in the formal baseline. It is introduced by the still-active predecessor; the isolated ordered composition below verifies it becomes available before this successor is applied. This is not a claim that the successor can be archived first.
- `openspec validate integrate-image-build-and-pve-publish --strict`: passed in actual infra-ops worktree.
- `openspec status`: proposal/design/specs/tasks complete for both changes; implementation tasks intentionally all unchecked.
- Local Markdown link audit: no broken cross-repo/file links; no implementation tasks falsely checked.
- Isolated `/tmp` copy only: archived `adapt-pve-ci-lifecycle` then this successor with normal spec validation. Six resulting touched specs each passed strict validation. This proves the dependency order and no scenario-dropping archive conflict; no actual repository was archived.
- Independent infra-ops `/tmp` copy: applied its delta with normal archive validation; all seven resulting specs passed strict validation. Informational long-requirement hints remain, not failures.
- Temporary archive printed expected unfinished-task warnings because the copies were used solely to test delta composition. No tasks were marked complete to bypass that warning.
- `git diff --check` and scoped new-file whitespace/link/status audits passed; no runtime tests are claimed for this documents-only task.

## Remaining implementation conditions

Installed-version API/permission/storage support, a qualified KVM executor, runtime/package pins, software tests, new site test window and representative end-to-end acceptance remain explicit future tasks. Upstream source review is not cohe live proof. No prior test window or prior permission to create one template/VM authorizes a new run here.
