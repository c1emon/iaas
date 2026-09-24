# Synthetic PVE lifecycle

This directory is a complete offline example for the versioned launcher. Every
host, endpoint, S3 bucket, key and image URL uses a reserved synthetic name.
`ssh_key.example` is deliberately unusable placeholder text. Replace the
runtime credentials and protected files in a caller-owned copy before any
online invocation; this checked-in example must never be pointed at a real PVE
cluster.

The VM root is under `root/`. Its `main.tf.json` declares exactly one
`bpg/proxmox` provider,
an explicit `synthetic-node` SSH node with `agent = false`, fixed HTTPS API/TLS
settings, and sensitive ephemeral variables for API and SSH credentials. The
separate `template/recipe.yml` is an independent template recipe; it is not
read from the VM root or VM inventory. `backend.json`, admission files and
`execution-result.json` are caller-owned transport examples. The latter keeps
the post-apply snapshot in one JSON file for a later `verify` call.

Prepare a caller copy with a resolved runtime image digest and protected input
modes:

```sh
cp -R docs/examples/pve-lifecycle /tmp/pve-lifecycle-review
chmod -R go-rwx /tmp/pve-lifecycle-review
```

Use a runtime selection owned by the caller. The digest below is only a shape
example and is not a release claim:

```json
{"interface_version":1,"image":"ghcr.io/example/iaas-runtime:vX.Y.Z","platform":"linux/amd64"}
```

The PVE state flow is read, plan, apply and verify. `read` observes the
caller-selected S3 object and current PVE objects; it only needs the root ID
metadata, so it does not materialize the root. `plan` materializes the complete
declared root, checks the provider lockfile, SSH trust and state admission, and
produces a native plan with its companion directory:

```sh
iaas run --runtime-config runtime.json \
  --environment environment.yml --engine local \
  --component pve --operation read --scope synthetic-root \
  --output ./pve-read

iaas run --runtime-config runtime.json \
  --environment environment.yml --engine local \
  --component pve --operation plan --scope synthetic-root \
  --output ./pve-plan
```

Review `pve-plan/plan/review.txt`, `review.json`, the provider binding and
snippet manifest. Apply consumes that exact native plan and all companions;
the execution ID is passed explicitly and the output directory uses the same
basename:

```sh
iaas run --runtime-config runtime.json \
  --environment environment.yml --engine local \
  --component pve --operation apply --scope synthetic-root \
  --execution-id pve-synthetic-apply-001 \
  --plan ./pve-plan/plan/plan.tfplan --companions ./pve-plan/plan \
  --output ./pve-synthetic-apply-001
```

After the caller has retained the resulting `pve-result.json` as
`execution-result.json`, verify uses the same plan and companions. The selected
result file can contain the original snapshot inline; no result directory is
implicitly discovered:

```sh
iaas run --runtime-config runtime.json \
  --environment environment.yml --engine local \
  --component pve --operation verify --scope synthetic-root \
  --plan ./pve-plan/plan/plan.tfplan --companions ./pve-plan/plan \
  --output ./pve-verify
```

If `execution-result` is omitted, verify records `unknown` with
`original_execution_material_missing` rather than claiming that the original
execution succeeded. `pve-result.json` remains a separate protected artifact;
validation or reporting exceptions must not overwrite it.

## Independent delete-plan check

`environment-delete.yml` selects `verification-root/`, a second complete root
whose resource is safe synthetic test data. Its `options.destroy: true` asks
the normal `pve plan` operation to create an ordinary delete plan. There is no
direct destroy operation. Apply still requires the reviewed plan, companions,
state admission and a fresh execution admission:

```sh
iaas run --runtime-config runtime.json \
  --environment environment-delete.yml --engine local \
  --component pve --operation plan --scope synthetic-delete-root \
  --output ./pve-delete-plan

# Inspect review.txt and confirm the exact VMID before any authorized apply.
iaas run --runtime-config runtime.json \
  --environment environment-delete.yml --engine local \
  --component pve --operation apply --scope synthetic-delete-root \
  --execution-id pve-synthetic-delete-001 \
  --plan ./pve-delete-plan/plan/plan.tfplan --companions ./pve-delete-plan/plan \
  --output ./pve-synthetic-delete-001
```

The checked-in admission example is for shape only and does not authorize a
real deletion. A caller must issue a new admission bound to the reviewed plan.

For a template still marked `pending_validation`, use a separate validation
root with `options.template_purpose: verification` and only `ephemeral_lab`
VMs. Its current template admission must set `purpose: verification`,
`approved: true`, `scope` to that root ID, and `vmids` to the exact ordered
VMID list in the plan's `template_use`. Normal VM consumption requires an
`available` admission. Publication remains a caller decision after validation.

## Independent image and PVE template publication

The current image and template lifecycle is defined by the
[image-publish-v1 contract](../../contracts/image-publish-v1.md). The complete
request, artifact, preview, result, cleanup and retire examples are kept in
[`docs/examples/image-publish/`](../image-publish/). These files are the
transport fixtures for the current HTTPS publisher; they do not describe the
old VM-root recipe or an SSH node helper.

Image build, test and clean are independent operations. `image check` is a
passive contract check that writes `diagnostics/normalized.json`; build and
test require the caller's Linux amd64/KVM executor. The artifact and test
result remain separate from PVE publication, and an external artifact may be
used when its descriptor and evidence satisfy the contract. Use the image
operation and field definitions in the contract rather than adding image
inputs to a VM-root environment.

PVE template publication consumes an immutable
`pve-template-publish-request/v1`, a reviewed `pve-template-preview/v2`, and a
complete execution admission. The publisher resolves the protected artifact
through `PVE_ARTIFACT_URL`, verifies the downloaded disk, and uploads it over
the PVE HTTPS API. `PVE_API_TOKEN` and `PVE_API_CA` are operation-scoped
runtime credentials. The private locator is never put into the PVE request or
logs, and the retired SSH helper/receipt protocol is not part of this path.

For a read-only observation, use
[`docs/examples/image-publish/environment-template-read.yml`](../image-publish/environment-template-read.yml).
It has no input documents; its `options.template` selects the fixed HTTPS
endpoint, node and VMID. The caller supplies `PVE_API_TOKEN` and, when needed,
declares `files.api_ca`; the launcher maps that file to `PVE_API_CA` inside the
runtime.

Plan and apply must use the same request, preview digest, target and execution
admission. Verify consumes the retained `pve-template-result/v2` and its
template record. Cleanup is a separate action using
`pve-template-cleanup-request.json`, a new preview and a new execution
identity; it is limited to publisher-owned, incomplete effects with current
inactive observations. A completed template is retired through
`pve-template-retire-request.json`, never removed through arbitrary cleanup.
Unknown effects, missing observations and lost responses remain pending for
reconciliation.

The old `docs/examples/pve-lifecycle/environment-template*.yml` files and
their `template/` materials remain only as regression fixtures that verify
the legacy protocol is rejected. They are not runnable instructions for the
current image/PVE lifecycle. The removed `prepare-plan`, `apply-saved-plan`,
`pve-plan`, `pve-apply`, `pve-destroy` and node-helper entrypoints must not be
used as compatibility paths.
