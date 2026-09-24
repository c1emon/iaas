## 1. Contract and baseline integration

- [x] 1.1 Confirm implementation branch and clean/preserved worktree according to repository rules; archive the completed `adapt-pve-ci-lifecycle` before applying its successor deltas, without changing old execution evidence.
- [x] 1.2 Implement versioned schemas and canonical preview binding from [contract](contracts/image-publish-v1.md); publish stable docs/schema locations and valid/invalid consumer examples.
- [x] 1.3 Add cross-repo fixtures for normalized descriptor equivalence (whitespace/key order), duplicate-key rejection, semantic/disk changes, independent test disk/policy mismatch, required checks, credentials, unknown results and ownership refusal.

## 2. Reusable image tool

- [x] 2.1 Extract existing Debian customization/identity-cleaning semantics from node worker into versioned profile/Ansible/offline routines; replace placeholder Packer asset with a real pinned QEMU builder. No PVE inputs in build configuration.
- [x] 2.2 Add direct image build/test/clean plus passive check/read/verify in the shared launcher, without prerequisite previews; use explicit KVM/work mounts, budgets and transient SSH, rejecting unsupported executor topologies.
- [x] 2.3 Implement local task records, process-group cancellation, bounded work/cache lifecycle and duplicate-active-ID prevention; clean appends to the original task under its resource lock without a new preview/recovery protocol. Preserve unknown ownership and collection failures.
- [x] 2.4 Implement build checks and independent image test for existing/external artifacts, using disposable guests and fresh UEFI VARS, with disk/policy-bound image-test-result/v1; preserve final offline cleanup/self-containment and immutable base checks. Cover missing KVM, bad checksum/backing files, NVRAM-only boot and interrupted cleanup.

## 3. HTTPS template publication

- [x] 3.1 Verify installed-version schemas/ACL requirements for import upload, VM config import-from, template/tasks/content delete and actual storage support; document constraints versus upstream evidence. Do not reuse the expired live-test window.
- [x] 3.2 Implement source resolution/streamed download with protected locator, TLS, byte bounds and SHA-256/format checks; never pass credential URLs to PVE or logs. Verify no cross-stage credentials enter runtime.
- [x] 3.3 Check publisher local and API-visible storage capacities/permissions; report unobserved PVE temp/proxy constraints without a new helper or automatic refusal. Test known insufficiency rejection, missing telemetry proceeding, and actual ENOSPC/413/timeouts with truthful effects.
- [x] 3.4 Implement task-unique import upload with preexisting-file refusal, VM create/import/config/template and UPID observation via official HTTPS. Test response loss, conflict, ENOSPC, native failure and template flag set before conversion failure.
- [x] 3.5 Change VM consumers directly to the new current-object/template record schema and current admissions, with independent config verification; verify VMID reuse, revoked admission and no implicit guest acceptance. Do not add a legacy adapter.

## 4. Cleanup and hard cutover

- [x] 4.1 Implement PVE cleanup/retire with current ownership/inactivity/dependency admission. Test publication succeeded + known static staging warning, durable separate cleanup todo before pending settlement, staging-only recovery, and refusal for unknown/activity/OpenTofu-owned objects or completed-template deletion outside retire.
- [x] 4.2 Replace template schema/build env generation, launcher help/discovery/examples and docs; reject old build previews/force paths, preserve raw old records for manual investigation without a compatibility reader.
- [x] 4.3 Deliver explicit old-worker drain/evidence-retention/uninstall migration; remove unused build binaries, storage ticket probe, packages and sudo rules only after dependency review. Preserve independent snippet helper.

## 5. Verification and paired rollout

- [x] 5.1 Run representative schema/unit/fake HTTPS integration, launcher isolation and migration regressions; run corresponding lint/build/OpenSpec checks. Do not equate API substitutes with live validation.
- [x] 5.2 On a caller-provided KVM executor, build one image and verify final identity cleanup with a disposable guest; record the exact supported environment. (ONE Linux amd64/Docker/KVM build and independent guest test passed; this direct test alone did not validate the later Runner.)
- [x] 5.3 Under a new explicit site window, validate one template publication and one disposable VM serially, including target storage and directory import; clean test resources and independently verify no unintended changes. (限定证据：r8 publication、VM799 create/destroy、retire、S3 cleanup 与现场观察均已记录；PVE VM 未启动来宾。)
- [ ] 5.4 Coordinate pinned runtime/schema handoff with infra-ops, validate a repeated publication of the same artifact without rebuild in an appropriately authorized scope, and document promotion/rollback/unknown-result recovery. (rc.13 runtime pins and one CI publication are verified; same-artifact repeat publication remains untested.)

Checkboxes track actual implementation and acceptance evidence. Planning review alone does not complete an implementation task; current progress and site limits are recorded in [implementation record](../../../docs/operations/image-publish-implementation.md).
