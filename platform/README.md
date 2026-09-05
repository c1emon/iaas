# Platform Boundary

`platform/` is a documentation-only boundary for handing a ready K3s cluster
to an independently operated external platform repository. It is not an
in-repository desired-state root and does not provide a compatibility alias for
one.

Ownership is deliberately split:

- This IaaS repository declares infrastructure, provisions reusable mechanisms,
  manages K3s node lifecycle, verifies readiness, and emits the non-secret
  handoff bundle.
- The external platform repository owns Flux and shared in-cluster desired state,
  including Cilium, CSI, Gateway, certificates, and observability.
- Application repositories own ordinary application releases, values, and
  application routing resources.

`platform/` SHALL NOT contain Flux, Cilium, CSI, Gateway, certificate,
observability, application manifests, Helm releases, reconciliation roots, or
production runtime configuration. Transport, signing, CI triggering, and
platform-side consumption of a handoff bundle remain outside this repository.
