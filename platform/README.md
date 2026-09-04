# Platform Boundary

`platform/` is reserved for future reusable in-cluster platform automation.
It intentionally contains no K3s installation, cluster bootstrap, GitOps,
Flux, Helm, workload, secret, or production-runtime implementation.

The current boundary is deliberate:

- `environments/astra/` declares the infrastructure composition.
- `automation/` provisions and validates reusable infrastructure mechanisms.
- A future platform change may consume a ready cluster through an explicitly
  designed interface, rather than coupling cluster automation to PVE inventory
  or VM lifecycle internals.

Adding K3s or any in-cluster capability requires a separate design and
OpenSpec change.
