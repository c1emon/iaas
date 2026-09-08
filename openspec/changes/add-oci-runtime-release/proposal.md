## Why

The selected Forgejo delivery model needs a versioned IaaS runtime that can run
without a checkout of this repository or its Astra configuration. Existing
automation is reusable, but its Make/Ansible resource paths, tool installation,
and environment OpenTofu module references are not yet a published container
contract. See `docs/decisions/forgejo-iaas-platform-delivery.md`, phase 3.

## What Changes

- Add one Linux OCI runtime containing the reusable Python implementation,
  Ansible resources, OpenTofu modules, and pinned execution dependencies.
- Package only runtime necessities. Exclude repository documentation, README
  files, OpenSpec, tests/fixtures, examples, CI configuration and build-only
  tools from the published image; retain required license notices and runtime
  metadata.
- **BREAKING**: Require explicit generic environment/output directory selection
  for environment operations in both checkout and container modes. Remove the
  `ASTRA` selector and implicit Astra path fallbacks; preserve operation names
  and domain schemas, and update supported callers.
- Define a stable image-local module location for externally owned OpenTofu
  roots and keep generated files, credentials, plan/state, and caches external.
- Publish versioned public images to `ghcr.io/<owner>/iaas-runtime` when a
  GitHub Release is published, after validation and container smoke checks.
- Report the source revision, release tag, and pushed image digest for private
  configuration repositories to pin; keep publishing separate from deployment.
- Verify representative synthetic workflows in the built image and document
  runtime invocation, release failures, reruns, and digest consumption.

## Capabilities

### New Capabilities

- `oci-runtime-delivery`: Portable runtime contents, external directory and
  module contracts, isolated validation, and Release-to-GHCR delivery.

### Modified Capabilities

- `iaas-repository-layering`: Separate reusable execution from named environment
  data, allow external roots, and remove implicit Astra selection.
- `pve-automation-foundation`: Generalize source/output locations for the
  selected environment, helper names and vault selection without changing VM
  validation, dedicated identities or lifecycle safety behavior.
- `iaas-validation-entrypoints`: Distinguish checkout validation, external
  environment operations, and the separate image publication workflow.
- `service-metadata-inventory`: Select service/VM inputs and generated document
  locations from the chosen environment instead of fixed Astra paths.
- `foundation-recovery-checks`: Generalize the generated recovery document path
  and source description without changing recovery metadata checks.
- `operator-documentation-entrypoints`: Document generic source/output selection
  and keep Astra examples specific to that environment.
- `pve-state-and-secret-operations`: Describe external runtime/state locations
  without treating historical Astra paths as portable runtime defaults.

## Impact

Expected areas are the root Makefile, `automation/ansible/ansible.cfg`, a small
runtime entrypoint and container build definition under `automation/`, PVE helper
names and their callers/sudoers/bootstrap declarations, dependency
pins, synthetic tests, `.github/workflows/`, and canonical operator documentation.
Existing Python CLIs already accept explicit files and should be reused.

There is no real Astra configuration migration, state migration, infrastructure
access, Forgejo installation, private apply pipeline, handoff correctness repair,
or platform bootstrap in this change. Standalone wheel/Collection/module-registry
products, multi-architecture qualification, signing systems, and automatic
Forgejo update PRs remain out of scope. This proposal is design-only until
implementation is separately started on the confirmed implementation branch.
