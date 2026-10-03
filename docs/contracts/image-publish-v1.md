# Image build and PVE publication contract v1

This is the stable consumer entrypoint for the image/PVE handoff. The
normative OpenSpec source is
[`contracts/image-publish-v1.md`](../../openspec/changes/archive/2026-09-29-separate-image-build-and-pve-publish/contracts/image-publish-v1.md);
the JSON schemas shipped below are the current machine-readable subset.
The current observation/deadline extension is specified in
[`add-pve-observation-executor-and-stop-diagnostics`](../../openspec/changes/add-pve-observation-executor-and-stop-diagnostics/design.md).

The stable schemas live under `automation/schemas/image-publish/v1/`:

- `image-build-request.schema.json`, `image-build-result.schema.json`, and `image-test-request.schema.json`
- `image-artifact.schema.json` and `image-test-result.schema.json`
- `pve-template-publish-request.schema.json`, `pve-template-preview.schema.json`, and `pve-template-record.schema.json`
- `pve-template-result.schema.json`, `pve-template-cleanup-request.schema.json`, and `pve-template-retire-request.schema.json`

The `v1` directory is the stable image-publish contract bundle version. It is
not a promise that every document inside the bundle has
`schema_version: 1`: each `kind` owns its own evolution. The build request is
version 2, the PVE publish request is version 3, cleanup/retire requests are
version 2, preview/result are version 4, and template records remain version 3. Use the `title` and `schema_version` in each schema for
the concrete document version, while keeping this directory and its `$id`
paths stable for the v1 bundle.

The shared launcher validates these documents with the same normalized
contract code at `src/iaas/image/contracts.py` and
writes `diagnostics/normalized.json` for `image check`. The file contains the
normalized document and `input_digest`; callers should bind that digest rather
than JSON formatting or object-key order.

Build requests require `disk_size_gib` (integer 8–1024), the output virtual
capacity, separate from physical `resources.max_output_bytes`. Bases larger
than the target are rejected before Packer; shrinking is unsupported. Final
QEMU capacity must match exactly and is recorded in `artifact.disk.virtual_size_bytes`.

`customization.package_upgrade` is an optional boolean, normalized to false.
When true, the builder refreshes the selected repositories and performs an
APT distribution upgrade. Failure fails the build before a successful artifact
is produced. Package versions come from repositories at build time; clones
need no first-boot upgrade.

Mandatory `hardware.bridge: null` explicitly selects no NIC. Omission or an
empty string is invalid. With null, `cloud_init_defaults.ip_config` must be
absent: creation sends no `net0`, verification rejects every `netN`, and the
record preserves absence. Cloud-init networking remains available to clones.

`check` validates local build, publication and PVE clone inputs, rejects
unsupported fields, wrong types, linked clones, disk shrink requests and
incompatible firmware, and identifies input file, field and reason without
echoing rejected values. It reads no credentials and performs no network or
facility operations. Actual base image capacity is verified on download in
build; checking a locator does not download its image.

Concrete cross-repository fixtures live under `docs/examples/image-publish/`:
the inline artifact, build request, image test result, publish request, preview,
complete execution admission and successful publisher result are all valid
inputs. The PVE admission uses the existing full `validate_execution_admission`
contract; its `plan_digest` is the lowercase digest without the `sha256:`
display prefix used by the native preview digest.

Image operations are direct local tasks:

```text
iaas run --component image --operation check|build|test|read|verify|clean
```

PVE template publication remains an admitted plan/apply lifecycle:

```text
iaas run --component pve-template --operation check|read|plan|apply|verify
```

Publication consumes a protected `PVE_ARTIFACT_URL` only in the publisher,
verifies the disk SHA-256 before the first PVE write, and never sends the
locator to PVE. Build history, template publication, guest acceptance and
caller promotion remain separate results.

For an existing template, `read` takes `options.template: {target, vmid}`
without an image request; the resulting observation keeps build history
unknown. Alternatively, select `files.journal` to inspect an original
publication journal. These selectors are mutually exclusive. `verify`
reads `files.result` and `files.preview` offline and checks their binding.
For HTTPS read/plan/apply with a private CA, declare `files.api_ca`; the
launcher maps it into the runtime as `PVE_API_CA`.

Publication, cleanup and retire requests require `deadlines.work_deadline_at`
and `deadlines.cleanup_deadline_at` as UTC seconds (`YYYY-MM-DDTHH:MM:SSZ`),
with work no later than cleanup. The normalized preview binds both cutoffs.
The generic execution admission remains version 1 and must repeat exactly the
request deadlines; its prefix-free `plan_digest` binds the selected preview.
For publication, the VMID reservation also binds cluster scope, selected VMID,
consumption reservation and serialization context. Example dates in 2099 are
synthetic placeholders; a real approval must select a finite current window.

All admitted reads and retries share the frozen operation budgets. Native
writes are dispatched once, and a UPID proves success only after
`stopped + exitstatus=OK`. Query failure, missing terminal outcome or deadline
expiry cannot establish failure/success of the underlying write.
`pve-template-result/v4` preserves `deadlines`, `deadline_outcome` and shared
`stop_diagnostics`: completed phases, stopping check, task activity, ownership,
existence, inventory completeness, bounded observations and recovery evidence
requirements. Overall unknown may retain a separately proven failed check.
The template record remains v3; it does not certify guest acceptance or caller
promotion. Original evidence is preserved when a new cleanup plan is approved.
