# Image build / PVE publish contract v1

Status: proposed; planning-only. Owner: iaas. Consumer: infra-ops [paired change](../../../../../infra-ops/openspec/changes/integrate-image-build-and-pve-publish/proposal.md). Paths here are logical CLI inputs/outputs, not deployed files. `v1` below is the contract edition; all schema discriminators are exact and unsupported versions MUST be rejected, never inferred from filename. This document is normative alongside the delta specs.

## 1. Operations and authority

Use the existing launcher dispatcher and common result conventions. Local image operations are direct tools, not deployment transactions; only PVE mutations require the plan/apply admission workflow. No second dispatcher or legacy aliases are introduced.

| Component / operation | Meaning | Effects / credentials |
| --- | --- | --- |
| image check | Offline request/profile/schema checks | local report; no network, KVM or credentials |
| image build | Validate and record selected configuration, then construct the image | local guest/files/network effects; only explicit source/package credentials; no prerequisite preview |
| image test | Test a selected existing image on a disposable guest | local guest/files/network effects, explicit check policy/budget; no PVE mutation or image rebuild |
| image read / verify | Read task/inspect existing image and retained evidence | private local reports; no guest start or image mutation |
| image clean | Clean stopped task-owned local resources by task selector | no new preview/execution admission; no shared cache/remote object deletion |
| pve-template check | Offline artifact/publication schema checks | no PVE or S3 access |
| pve-template read / plan | Observe explicit target; plan action=publish, cleanup or retire | HTTPS reads and private preview only; no image download/upload/VM writes |
| pve-template apply | Execute exact reviewed action | API writes; current execution admission and operation credentials required |
| pve-template verify | Read bound template/task/config evidence | no repair, no guest start, no S3/state mutation |

`packer validate` and template publication previews are not OpenTofu native saved plans. Local image build/test captures its actual normalized input at start and needs no PVE target/admission/backend, separate review artifact or once-consumed deployment plan. Caller-local serialization and task isolation still apply. Publication uses existing execution_admission (approved, reserved single consumption, pending persisted, lock held) bound to target/preview/execution. Caller owns cross-run serialization and ledger; iaas owns its local task journal and validates associations. No `OP_SERVICE_ACCOUNT_TOKEN`, runner registration secret or Docker client certificate enters either runtime.

The caller supplies a private persistent execution directory per execution_id, retained independently of an ephemeral container and collected before deletion. This is iaas journal storage, not the caller's consumption ledger. Publication polling can disconnect while the task continues; recovery must retain the original journal and use the same endpoint/identity or explicitly admitted read-capable recovery identity. No journal means no reconstructed historical success.

### Selectors and action-specific recovery inputs

Read/verify selectors are typed and mutually exclusive; missing/ambiguous selectors fail, never select all. `image read` takes execution_id plus execution_dir; `image verify` takes artifact.json, artifact_root and optional selected build result/check evidence, and never reruns boot checks. `pve-template read` selects either original execution journal or exact target+VMID for fresh observation; `pve-template verify` requires selected preview, result/template_record and exact target. A fresh observation can produce a new record but cannot substitute for the original execution's result.

`image clean` takes execution_id and execution_dir and optionally a subset of resource refs from that task record, not arbitrary paths. It acquires the same local task resource lock, rechecks ownership/inactivity and appends a cleanup-attempt result to that task. It needs no separate cleanup-request schema, preview, new execution_id or recovery_of. Missing/unknown ownership still blocks deletion. Shared cache and delivered caller-owned artifacts are excluded; repeated clean of proven already-removed resources may report cleaned without error. A dry-run may show candidates but is not an admission token.

`kind=pve-template-cleanup-request,schema_version=1` requires target, original_execution_id, original_execution_dir, original_preview_digest, selected objects/volumes from the journal, and current ownership_admission{owner,reference}. `kind=pve-template-retire-request,schema_version=1` instead requires target, selected new-schema template_record, current ownership_admission and retirement_admission{authorized,dependencies_resolved,reference}. These are trusted caller declarations bound to exact native identities; missing/unknown/false assertions block destructive actions. `owner` is publisher|opentofu|unknown; only publisher permits deletion. Runtime independently checks observable object/task facts and dependencies; caller declarations do not override a conflict. Publication actions also require current execution_admission.

PVE cleanup/retire plan freezes current identities (UUID, volumes, known tasks), selected deletion set, admission references, runtime/target and originating association. Apply gets fresh admission bound to preview_digest and new execution_id; PVE cleanup requires recovery_of, ordinary retirement of an adopted existing template need not fabricate an original build execution. A staging-only cleanup may reference a completed publication but MUST NOT delete its completed template; the latter requires retire. Unknown upload outcomes require explicit reconciled ownership before any file can enter a new cleanup preview.

## 2. Build and independent test inputs

`kind=image-build-request`, `schema_version=1`:

| Field | Meaning / constraint |
| --- | --- |
| profile{id,version} | Versioned iaas-supported build recipe, initially debian-13-amd64; not arbitrary HCL or shell |
| version | Caller display/release version; not proof of identity |
| base{object_ref,checksum{algorithm,value}} | Stable credential-free HTTPS/object identity, checksum sha256 or sha512; no mutable implicit latest |
| guest{architecture,firmware} | Initially amd64 and bios/uefi; no implicit host-derived architecture/firmware; x86_64 is a QEMU-internal name only |
| customization | Typed apt_mirror, apt_security_mirror, packages, timezone, locale and supported profile settings; package lists are data, not shell fragments |
| resources{cpus,memory_mib,work_min_free_bytes,max_output_bytes,timeout_seconds} | Positive bounded executor budget; includes offline tool and disposable verification resources |
| checks{required,optional} | Fixed check IDs and scope from supported profile; failures/unknown of required checks block successful delivery |

Build validates the request and captures normalized input, runtime_digest and profile/config identity in its task record at invocation. This is execution provenance, not an approval preview; no image-build-preview schema or image plan/apply is required. Tool/plugin versions are pinned by runtime/profile. Offline check does not claim working KVM; build/test validates actual KVM startup and resource availability when starting its guest. Transient authentication is provided separately. An existing task ID cannot overwrite a different request or start a duplicate active task; deliberate reruns use a new task ID without requiring another approval plan.

`kind=image-test-request,schema_version=1` requires artifact, artifact_root, checks{required,optional}, and resources (the same bounded resource fields as build). It accepts a supported existing or externally built image without rebuilding or modifying it, validates actual disk SHA-256/format/self-containment, records the selected test policy/runtime, then uses a disposable copy/overlay and fresh UEFI VARS when applicable. Read/verify remain passive; test is explicitly local guest execution. Results use `kind=image-test-result,schema_version=1` with execution_id, disk_sha256, test_config_digest, runtime_digest, checks[], base_unchanged and cleanup. Only matching disk digest/policy/scope and passed checks can supply new acceptance evidence; testing does not invent earlier build/cleaning history.

## 3. Local artifact

`kind=image-artifact`, `schema_version=1`, produced as `artifact.json` with `disk.qcow2` and `disk.qcow2.sha256`:

| Field | Meaning / constraint |
| --- | --- |
| artifact_id, version | Stable caller identifiers; hashes, not labels, bind content |
| disk.path | Relative path inside explicit output root; reject absolute paths, traversal and symlink escape |
| disk.format | qcow2 (single disk in v1) |
| disk.sha256 | Lowercase 64 hex characters over final delivered bytes |
| disk.size_bytes, disk.virtual_size_bytes | Actual file bytes and guest disk capacity; both positive, independently observed |
| disk.self_contained | MUST be true and verified by image inspection: no backing/external data file; metadata declaration alone is insufficient |
| guest.architecture, guest.firmware | amd64; bios/uefi as fixed and checked by profile |
| guest.cloud_init, guest.guest_agent | installed/absent/unknown; installation is not runtime readiness |
| build | For this tool: recipe_id, recipe_version, runtime_digest, config_digest, execution_id; external artifacts may use origin=external with unavailable facts null/unknown |
| checks[] | id, scope, status(passed/failed/not_performed/unknown), evidence_ref; refs are relative to supplied evidence bundle or explicit retained caller evidence, never credentials |

Required image checks: actual format/size/self-containment, declared firmware compatibility and fixed profile's cleanup checks. Readiness is separate: a check records whether it ran before cleanup, on a disposable post-cleanup guest, or on disk statically. No live guest readiness is inferred from installed packages. Image publication request defines required evidence; external build origin does not bypass it or fabricate history.

For publication, resolve required checks from the artifact plus explicitly selected test_results. A matching disk/policy/scope passed test may satisfy a check previously not_performed or unknown in the artifact; the original descriptor and its history remain unchanged. Missing historical evidence is not conflicting evidence. Actual conflicting observations cannot be silently overridden by the latest result; require an unambiguous selected evidence set under the fixed check policy. Tests cannot establish unrelated historical claims such as how the original image was built.

Checksum is computed after all changes/cleanup; final source disk MUST NOT be booted or modified afterward. Post-cleanup checks during build or independent test use a disposable overlay/copy, and the base is checked again afterward. For UEFI, tests MUST use fresh variable storage: the qcow2 must boot without Packer's build-time efivars.fd/Boot entries, which are not deliverable dependencies. Secure Boot key enrollment is outside v1. Artifact output is atomic at task scope: an incomplete disk/report never carries build status succeeded; keep failure evidence separate. SHA files use standard sha256sum syntax. No new signature/attestation service is required.

## 4. Caller upload and cross-repo handoff

infra-ops uploads the disk and required check evidence under a selected immutable object key/version, verifies standard transfer completion, object size and exact object identity, then publishes the descriptor as the handoff completion point. Record uploaded status separately from independently content_verified status. Use native transfer/checksum facilities when available; multipart ETag alone is NOT SHA-256 evidence. A full post-upload GET/hash is an optional site assurance step, not a default prerequisite. The publisher MUST still download and verify actual disk SHA-256 before any PVE write; successful transfer or size alone never bypasses that check. Failed/incomplete uploads never advance publication.

Descriptor content is schema-validated and semantically bound; reformatting or object-key ordering is not an input change. Stable object_ref and object_version are carried separately in the publish request, not written into disk.path. Successful upload does not imply a usable PVE template. S3 auth resolution, URL issuance, upload/retention and promotion belong to infra-ops. Shared cache reuse does not transfer ownership to the last task. A retry of publication consumes the same selected disk digest; it never triggers rebuilding.

## 5. Publication input and immutable association

`kind=pve-template-publish-request`, `schema_version=1`:

| Field | Meaning / constraint |
| --- | --- |
| artifact | Complete image-artifact/v1 descriptor (inline or selected file) |
| artifact_digest | SHA-256 of the schema-validated normalized descriptor; key ordering/whitespace changes do not require a new preview |
| test_results? | Explicit additional image-test-result/v1 evidence bound to this disk and required scope; included in normalized publication input, never silently chosen as latest |
| source{object_ref,object_version?} | Stable credential-free exact disk object; no aliases whose resolution changes at apply |
| target{api_endpoint,node,tls_verify} | Fixed HTTPS API origin/target, tls_verify=true; no userinfo/query/fragment |
| vmid, version, name | Explicit free VMID and separate template version, constrained by admitted site scope |
| staging_storage, disk_storage, cloud_init_storage, efi_storage? | Explicit stores; content, accessibility and actual operation support checked; EFI required only for uefi |
| hardware | cpus, memory_mib, machine, scsi_controller, boot_disk, bridge and guest-derived firmware; supported schema, no raw QEMU args |
| cloud_init_defaults | Explicit non-secret defaults; no build credentials or instance identity baked into disk |
| requirements | required/optional artifact checks, mandatory native template-config verify, guest acceptance scope/caller responsibility |
| transport | controller-upload only in v1 |

The concrete `requirements` object uses `required` and `optional` arrays of `{id, scope}` check selectors, `native_template_config_verify=true`, and `guest_acceptance_scope="caller"`. The two arrays and `test_results` default to empty arrays in normalized output; duplicate or overlapping selectors are invalid. Check evidence is matched by both ID and scope, and selected independent tests must bind the selected disk and test policy. These names are shared by both repositories; consumers do not translate alternative field names. `artifact` is the complete normalized descriptor in the materialized request; a JSON `$ref` placeholder is not a descriptor instance. Stable `source.object_ref` may be a credential-free exact HTTPS URL or `s3://bucket/key`; the transient HTTPS locator is supplied separately at execution and is never part of the preview.

Transient inputs at execution: PVE API token/CA, protected HTTPS artifact locator and optional trust for its origin. Publication does not require SSH or a space helper. These secrets are not fields in artifacts/previews or ordinary command argv/logs. Source redirect/proxy/trust behavior is explicit and fail closed; reissued locator may change expiry/signature only while remaining bound to selected stable source and exact digest. Never send signed/private source URLs to PVE download-url (upstream logs full URL).

`kind=pve-template-preview,schema_version=2` contains action=publish|cleanup|retire, normalized fixed_input, artifact_digest+disk digest (publish), exact target/runtime identity, mandatory requirements, preview_digest, observed capabilities and advisory capacities. PVE cleanup/retire instead bind original execution/current native objects, current management/dependency facts. Previews use canonical JSON digest binding with their own digest excluded. Descriptor/selected test results use the same normalization: reject duplicate keys, unknown schema fields and invalid numeric values; apply declared defaults; serialize all semantic fields as UTF-8 JSON with recursively sorted keys, no insignificant whitespace and unescaped Unicode. v1 fields use strings, integers, booleans, null, arrays and objects, not floating point. No allowed semantic field is omitted from the digest. Provide shared fixtures/CLI output for consumers. Disk SHA-256 still binds exact image bytes. Semantic changes require new plan; mere JSON formatting does not. Conflicting test evidence or evidence for another disk/scope is rejected, never silently substituted. Apply has no mutable input override; recheck mutable preconditions under caller lock.

## 6. HTTPS publish sequence and ownership

Before mutation: caller admission/pending/lock → query complete VM inventory with adequate read authorization → capacities/trust/ACL/storage/bridge/firmware check → create durable local execution journal. Stream download and verify artifact size/digest/format/self-containment before any PVE write. Allocate staging filename from strict execution ID plus disk digest; ensure it does not exist and serialize the staging namespace. PVE upload overwrites existing names: same checksum is NOT permission to overwrite/reuse. A conflict requires a fresh reviewed execution/filename or proven ownership recovery.

Then perform upload(content=import, checksum) → create VM → import disk via PVE storage volume ID → configure boot/Cloud-init/EFI → convert template → verify. Each applicable UPID MUST reach stopped with exitstatus OK before dependent steps. `template=1` alone is insufficient because PVE sets it before disk conversion; independently verify bound volumes/configuration as well. Final storage format follows supported backend; source qcow2 does not require final disks to remain qcow2.

Permissions MUST cover the complete lifecycle: read inventory/config/tasks/storage, allocate/create/configure disks and VM, convert and delete own objects, upload import files and DELETE import content. Specifically upstream upload needs Datastore.AllocateTemplate while import DELETE needs Datastore.Allocate; source import volume needs Audit or AllocateSpace. Scope such storage permissions to a dedicated staging store. Task ownership permits reads; recovery under a different identity requires adequate task-read rights. Do not request exact root@pam for arbitrary source filesystem paths.

Default capacity checks cover the publisher's local filesystem and API-visible import/destination storage; use disk virtual size for destination allocation and aggregate shared usage where known. Known insufficient capacity, explicitly incompatible storage/API and known upload limits block dependent work. PVE upload temp space and any proxy limits remain documented site deployment constraints with conservative budgets and optional monitoring. Missing precise observation of receiving-node `/var/tmp`, filesystem sharing or proxy limits is reported as unobserved, not as verified sufficient and not by itself a publication blocker. Do not introduce SSH/helper privileges just to prove those facts. Resolve the API target/trust normally; lack of temp-space telemetry does not mean target ambiguity is allowed. Handle actual ENOSPC, upload rejection or timeout using the normal known/unknown result and cleanup rules. Site-specific deeper space probing may be proposed separately; it is not implemented or required in this change.

## 7. Results, interruptions and cleanup

### Concrete shared field shapes

Both repositories consume the same native fields; transport/ledger metadata does not rename or reshape them:

| Field | Native JSON shape |
| --- | --- |
| `preview_digest` | Canonical digest carried by the selected PVE preview. A raw file SHA used by the caller's material store is separate metadata. |
| `effects` | Object mapping resource classes to `none`, `known` or `unknown`; not a scalar. Any relevant unknown class prevents settlement as a known successful publication. |
| `publication` | String `succeeded`, `failed`, `unknown`, `not_performed` or `not_applicable`; cleanup/retire use `not_applicable`. |
| `collection` | Object with `status`: `succeeded`, `failed`, `unknown` or `not_performed`. Success means required local result material was durably collected, not that the caller has already uploaded it. |
| `cleanup` | Object with `status`: `succeeded`, `failed`, `unknown` or `not_required`, plus a `residue` array of exact task-owned resource references. |
| `verification` | Array of check observations with `id`, `scope`, `status` and nullable `evidence_ref`; never a substitute for the native mutation result. |

The PVE configuration observation uses `id="template-config"` and `scope="pve-api-config"`. The template record's separate verification object keeps the field `template_config`; consumers must not confuse that field name with the observation ID.

For the successful-publication staging exception, `cleanup` additionally carries `scope="staging-only"`, `inactive=true` and `todo` containing the original execution association and exact residue selected for later cleanup. These facts must come from the journal and native task observations; the caller cannot manufacture them from `cleanup.status=failed` alone. The caller durably retains this todo before settling pending. A later cleanup still obtains its own current admission.

Image test results use `base_unchanged` as boolean or null (unobserved). Structural result validation accepts failures, interruptions, false/null base observations and incomplete cleanup so those facts can be saved/read. Publication evidence admission, separately, accepts only matching passed checks with a confirmed unchanged base and sufficient terminal evidence.

Artifact `build.origin` is `iaas` or `external`; omission is normalized to `iaas`. `evidence_ref` may be null when no retained evidence exists. Null or omitted evidence is not fabricated history.

PVE execution admission reuses the existing versioned execution-admission contract: `schema_version`, `execution_id`, `plan_digest` (the native preview digest), exact `target`, `approved`, `consumption{reserved,reservation_id}`, `pending{record_id}` and `serialization{held,context_id}`. These declarations come from the caller's actual approval/reservation/pending/lock state. Recovery additionally binds `recovery_of` and the original `pending.execution_id`. Neither a standalone `pending_before_apply` boolean nor an independently invented admission kind replaces these fields.

`image-build-result/v1`, `image-test-result/v1` and `pve-template-result/v2` use execution_id, component, operation, runtime_digest, phase, status(succeeded/failed/interrupted/unknown), effects(none/known/unknown by resource class), verification[], collection and cleanup. Local build/test adds input_digest, not preview_digest/admission; local clean appends an attempt under its original task. PVE adds action, preview_digest, publication and recovery_of where applicable. Native UPIDs and disk/object observations remain private details with a safe summary projection. Optional tests are explicitly not_performed; required image/template checks and uncertain mutation outcomes still block the associated success. Known staging-cleanup residue is reported separately as specified below.

A publication result includes artifact_digest/disk digest and a template_record with kind=pve-template-record, schema_version=2, record_id, target, node/VMID/SMBIOS UUID, volume references, key config, original execution and verification scope. VM consumers MUST directly consume this new schema with current template_admission; no old-record adapter is provided. Fresh observation of an existing template uses the same new record schema, origin=observation, with unavailable artifact/build execution facts explicitly unknown. build_result != upload_complete != template_config_verified != guest_accepted != caller_promoted.

Write phase intent before request, journal UPID immediately after response. A timeout before response can mean accepted-but-unobserved; keep unknown effects/pending, do not retry POST automatically. Reconnect reads original tasks/objects; if uniquely attributable completion cannot be proved, remain unknown even when current config matches. Missing/failed collection cannot erase native facts or report complete success. Execution ID dedup is local/caller authority, not a claim of PVE exactly-once support.

Controlled local build cancellation terminates owned process groups and waits; PVE cancellation of the controller only stops waiting. Cleanup requires confirmed original activity stopped and current publisher ownership. Lost response on upload cannot authorize deleting a similarly named file. Cleanup result is separate from original apply result. Local disk/seed/key/QEMU cleanup belongs to image; exact staging/import volumes and incomplete VM cleanup belong to publisher. Unidentifiable internal `/var/tmp/pveupload-*` files remain PVE/maintainer recovery scope, not arbitrary-root-delete capability.

OpenTofu-owned or uncertain objects MUST be rejected by publisher cleanup. Full template deletion uses retire with current retirement/dependency admission; unresolved dependent clones block it. No implicit S3 deletion or published template overwrite. When all native mutation tasks are stopped, template creation/conversion/config verification succeeded, result collection is complete and the only residue is an exact known-owned inactive staging file, report status=succeeded, publication=succeeded, cleanup=failed plus a warning and residue list. Template consumption is not blocked solely by that residue. The caller persists the terminal publication result and a separate cleanup todo before settling publication pending; no global lock/pending is retained solely for those static leftovers. Later staging cleanup uses a new PVE cleanup plan/execution/recovery_of and must not select the completed template. Unknown task activity/ownership, inadequate template verification, lost result collection or ongoing writes retain non-success/pending. This exception does not weaken VM/state/OPNsense recovery or allow unowned deletions. PVE recovery mutations still require a new preview/execution and current admission, never replay the original write.

## 8. New contract cutover

Build schema and publication schema are independently versioned. Missing/unsupported schema, runtime, profile or template record fails before mutation. `pve-template action=build`, preview v1 and bundled node customization are rejected after cutover; no legacy aliases, translation adapters or duplicate paths. Old raw records are retained for manual investigation; new tools need not parse them. Existing templates may receive fresh new-schema observations that only prove current facts. VM consumer inputs move directly to the new template record; OpenTofu native state/plan and OPNsense native formats remain independently validated.

The paired changes must be schema/field/negative-case reviewed together before implementation. Release must provide stable schema/docs and reference examples that infra-ops can pin without cloning iaas implementation. Retiring old helper requires no active tasks, retained old evidence and reconciled ownership/pending; planning this migration does not authorize its execution now.
