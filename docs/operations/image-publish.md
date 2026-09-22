# Image build and PVE template publication

The image and template paths are separate operations. The image tool receives
`image-build-request/v1` or `image-test-request/v1` and stores task material
under the caller's private output directory. `image check` is passive and
writes `diagnostics/normalized.json`; build and test require a Linux amd64
executor with usable `/dev/kvm`. A macOS or ordinary arm64 container is an
unsupported executor and cannot be treated as a successful build check.

The image output is `generated/artifact.json`, `generated/disk.qcow2` and
`generated/disk.qcow2.sha256` within the task output when the image executor
completes. `image test` produces `generated/test-result.json`. `image clean`
accepts the original task identity and execution directory and removes only
task-owned temporary resources; it does not remove a delivered artifact or a
shared cache.

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
