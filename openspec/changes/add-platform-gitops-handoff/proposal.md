## Why

The K3s capability can prepare and verify a bootstrap-ready cluster, but the
repository has no explicit contract for transferring control to a separately
owned platform repository. Without that boundary, platform bootstrap may copy
cluster facts, pass kubeconfig through ad-hoc files, or accidentally make the
IaaS repository own Flux and application reconciliation.

The existing repository-layering specification also reserves `platform/` for
future in-repository implementation. That ownership statement must be revised
to match the selected external platform-repository model.

## What Changes

- Add a small GitOps handoff contract that composes an explicit platform
  repository locator with the already validated K3s model.
- Require a same-model, same-scope read-only K3s verification before producing
  an online handoff bundle.
- Derive cluster identity, API endpoint, and K3s version from the validated K3s
  model. Read the authoritative K3s server CA through the existing
  authenticated guest path and verify the API endpoint against it before
  emitting its SHA-256 fingerprint.
- Do not copy VM, PVE, token, or kubeconfig values into handoff intent.
- Carry only an external bootstrap-credential reference. The platform
  repository receives the operator-supplied bundle, resolves the credential
  through its own protected runtime path, validates that access against the
  bundle endpoint and CA identity, installs Flux, verifies first
  reconciliation, and then revokes the independent temporary grant so it can
  no longer authenticate to the cluster.
- Keep Flux, Cilium, CSI, Gateway, application manifests, and cross-repository
  CI invocation outside this repository.
- Update the repository-layering boundary so `platform/` remains documentation
  for the external ownership contract rather than a future in-cluster
  implementation root.
- Synchronize current repository and K3s platform-design documentation with the
  external three-way IaaS/platform/application ownership model.
- Use synthetic fixtures and software-only tests; do not contact or mutate a
  real cluster while implementing this capability.

## Capabilities

### New Capabilities

- `platform-gitops-handoff`: Defines a fail-closed, non-secret handoff bundle
  and readiness boundary for an independently operated platform repository.

### Modified Capabilities

- `iaas-repository-layering`: Changes future in-cluster platform ownership from
  this repository to an explicit external repository handoff boundary.

## Impact

- Expected implementation areas: a narrow handoff validator/renderer under
  `automation/src/iaas_automation/`, explicit offline and
  infrastructure-read-only Make entrypoints, synthetic fixtures/tests,
  operator documentation, the current K3s platform-design document, and the
  repository/platform documentation indexes.
- Existing VM inventory, generated PVE inventory, K3s intent, K3s deployment,
  and platform repository schemas remain independent.
- The IaaS workflow validates only recognized external-reference syntax for
  bootstrap access and never contacts a secret provider or resolves the
  referenced value. The reference must identify an independently revocable
  temporary access grant rather than a shared long-lived administrator identity.
- The rendered handoff bundle is an operator artifact, not committed
  environment state. It contains no token, kubeconfig, private key, repository
  credential, or platform manifest.
- Bundle delivery is an explicit operator/platform-pipeline input; transport,
  signing, artifact publication, and cross-repository triggering remain outside
  this change.
- `make check` remains offline-only. Handoff readiness is an explicit
  infrastructure-read-only operation with a local protected-artifact write and
  never installs Flux or applies platform resources.
