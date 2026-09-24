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

## Independent template recipe

Template operations use `environment-template.yml` and the node helper
protocol. Build planning records a fixed recipe in `template-preview.json`;
apply accepts that exact preview and an admission bound to its digest. The
target always names one explicit node:

Online operations use the fixed SSH helper with explicit key and known_hosts
files. Caller-supplied helper commands are not supported.

```sh
iaas run --runtime-config runtime.json \
  --environment environment-template.yml --engine local \
  --component pve-template --operation check \
  --output ./template-check

iaas run --runtime-config runtime.json \
  --environment environment-template.yml --engine local \
  --component pve-template --operation plan --scope synthetic-node \
  --output ./template-plan

iaas run --runtime-config runtime.json \
  --environment environment-template-read.yml --engine local \
  --component pve-template --operation read --scope synthetic-node \
  --output ./template-read

iaas run --runtime-config runtime.json \
  --environment environment-template-apply.yml --engine local \
  --component pve-template --operation apply --scope synthetic-node \
  --execution-id template-synthetic-apply-001 \
  --output ./template-synthetic-apply-001

iaas run --runtime-config runtime.json \
  --environment environment-template.yml --engine local \
  --component pve-template --operation verify --scope synthetic-node \
  --output ./template-verify
```

The apply entry selects the checked preview and pins its digest in
`options.preview_digest`. In a caller copy, replace that preview with the
reviewed `template-plan/plan/template-preview.json`, copy its digest into the
apply entry, and transfer the independent execution admission bound to the
same digest. The result's `diagnostics/receipt.json` is a bare template
receipt; `generated/template-records.json` is the separate VM-plan input.
Copy the bare receipt into the caller's selected `template_receipt` file
before running verify; keep the remote observation separately if no complete
receipt was collected, and leave that execution pending/unknown.

Cleanup is a separate recipe action. The checked synthetic cleanup entry
binds the failed execution, exact object, helper ownership, stopped management
state, runtime image digest and helper protocol:

```sh
iaas run --runtime-config runtime.json \
  --environment environment-template-cleanup.yml --engine local \
  --component pve-template --operation plan --scope synthetic-node \
  --output ./template-cleanup-plan

# Copy the reviewed plan/template-preview.json into the caller-owned cleanup
# apply entry and update its options.preview_digest before the authorized run.
iaas run --runtime-config runtime.json \
  --environment environment-template-cleanup-apply.yml --engine local \
  --component pve-template --operation apply --scope synthetic-node \
  --execution-id template-synthetic-cleanup-001 \
  --output ./template-synthetic-cleanup-001
```

`template-cleanup-admission.json` is bound to that exact cleanup preview and
new execution identity. A real caller must issue a fresh admission after
reviewing the generated preview.

If a build failed before creating a VM, cleanup can remove that execution's
cache/work only when its record confirms no VM effects and a fresh node
observation confirms the VMID is absent. Unknown effects or a reused VMID
block this path. Original execution records, receipts and logs are retained;
cleanup writes its own success or failure receipt.

The example is a contract and transport fixture. It covers launcher discovery,
file selection, schema validation, synthetic state and helper substitutions.
It does not cover a real PVE API, SSH handshake, S3 lock, node helper,
cloud-init upload, guest verification or business acceptance. Container and
DinD checks prove the selected-file transfer and process boundary only; they
do not qualify a facility or a shared CI environment.

The old `prepare-plan`, `apply-saved-plan`, `pve-plan`, `pve-apply` and
`pve-destroy` entrypoints are migration errors. Use the four PVE lifecycle
operations above and express deletion through `options.destroy: true`.
