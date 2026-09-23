# Image build and PVE template publication

The image and template paths are separate operations. The image tool receives
`image-build-request/v1` or `image-test-request/v1` and stores task material
under the caller's private output directory. `image check` is passive and
writes `diagnostics/normalized.json`; build and test require a Linux amd64
executor with usable `/dev/kvm`. A macOS or ordinary arm64 container is an
unsupported executor and cannot be treated as a successful build check.

The image executor keeps its task directory under
`work/image-tasks/<execution-id>/`. A successful build writes
`artifact.json`, `disk.qcow2`, `disk.qcow2.sha256`, and `build-result.json`
there; a test writes `test-result.json` in the same directory. These are task
records and materials, rather than files in the top-level `generated/`
category. `image clean` accepts the original task identity and execution
directory and removes only task-owned temporary resources; it does not remove
a delivered artifact or a shared cache.

PVE publication consumes `pve-template-publish-request/v1` and a selected
`pve-template-preview/v2`. The publisher resolves the fixed credential-free
HTTPS or S3 object reference through a protected `PVE_ARTIFACT_URL` locator,
downloads it into its private task directory, verifies size and SHA-256,
then uploads through the PVE HTTPS API using a task-unique filename. It does
not send the private locator to PVE and does not use SSH or the retired node
template helper. `PVE_API_TOKEN` is operation-scoped; `PVE_API_CA` may point to
the caller's protected CA file.

Successful technical publication writes `diagnostics/result.json` and
`generated/template-record.json` (`pve-template-record/v2`). The record proves
the current PVE identity and configuration only. Guest acceptance and caller
promotion remain separate. A lost response leaves effects unknown and must be
read/reconciled under the caller's pending and serialization context; it is
never replayed from a fresh execution ID.

## Promotion, revocation, rollback and unknown results

IaaS reports technical publication only. The caller owns the availability
registry and promotion decision: a `pve-template-record/v2` may be marked
available only after the caller's declared configuration, clone and business
checks have passed. Promotion records the exact template identity, artifact
digest, runtime/schema pins and evidence scope; it does not update existing
VMs or imply guest acceptance that was not performed.

Revoking a promoted version is a caller registry change. It should stop new
consumers while retaining the artifact, publication result and template record
for investigation. Removing a PVE template is a separate `retire` operation
with current ownership and dependency admission; revocation never authorizes
deletion by itself.

Software or runtime rollback requires draining the affected execution path,
retaining its journals and results, and selecting the previous known-good
launcher/runtime/schema pins. It does not replay a consumed admission, repeat
a POST, rebuild the artifact, or automatically alter existing templates or
VMs. Any new publication, cleanup or retirement after rollback needs a fresh
request, preview and execution admission.

If an apply response or result collection is lost, keep the original pending
execution and journal as `unknown`. Reconcile the original UPID and exact
objects under the caller's serialization context; do not infer success from
current configuration or create a fresh execution ID to retry the mutation.
Only after an unambiguous reconciliation may the caller create a new cleanup
or retirement preview, with `recovery_of` where required. An unresolved
unknown remains pending for manual recovery.
