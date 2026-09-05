## Why

The repository can create and baseline Debian cloud-image VMs, but it has no
repository-owned capability to validate, deploy, verify, or maintain K3s on
those hosts. The next step is to add that reusable automation boundary without
declaring Astra K3s nodes or deploying a live cluster.

## What Changes

- Add a compositional K3s cluster contract: the K3s overlay references hosts
  from an operator-selected generated Ansible inventory and selects one generic
  VM NIC role for cluster-wide node identity, while
  VM-owned facts such as host identity, CPU architecture, connection address,
  NIC address, prefix, subnet, gateway, DNS, resources, template, and PVE
  placement remain owned by VM/template inventory
  rather than repeated manually.
- Add canonical architecture metadata to existing VM template declarations and
  regenerate the derived `pve_architecture` host fact; do not add K3s roles or
  topology to VM inventory.
- Add offline validation and redacted configuration rendering for pinned K3s
  versions, embedded-etcd topology, server/agent roles, bootstrap order,
  derived node identity, cluster networking, component policy, and external
  secret references.
- Add reusable Debian Ansible workflows for K3s host preflight, server/agent
  deployment, bootstrap-level verification, protected embedded-etcd snapshot,
  and controlled upgrade.
- Add an explicit pinned-artifact source and action-scoped proxy/authentication
  path shared by artifact preflight and acquisition.
- Add K3s/containerd registry-mirror and service-proxy policy, including explicit
  upstream-fallback enforcement, verified TLS material, derived bypass ranges,
  explicit retirement, and runtime secret references. Treat APT access as a
  read-only host prerequisite rather than taking ownership of generic guest
  package-source configuration.
- Separate offline-safe, online read-only, and mutation-capable commands; require
  explicit configuration, inventory, and host scope for online operations, plus
  action-specific runtime secrets for any online path that requires them.
- Add only synthetic K3s fixtures and software-level evidence in this change.
  Apart from migrating existing template architecture metadata and its generated
  host fact, do not add real Astra K3s nodes, modify live infrastructure, or claim
  a working cluster.
- Keep Cilium installation, Flux, CSI, Gateway, application workloads, external
  datastores, SQLite datastore support, automatic restore, uninstall, and
  destructive node-removal automation outside this change.
- Keep Debian APT source/proxy management and global shell or Git proxy
  configuration outside this change; those belong to a separately reviewed VM
  baseline capability if required.

## Capabilities

### New Capabilities

- `k3s-automation-operations`: Defines reusable, fail-closed K3s deployment,
  verification, snapshot, and controlled-upgrade automation without coupling it
  to a real environment deployment.

### Modified Capabilities

- `pve-automation-foundation`: Adds a template-derived VM architecture fact to
  normalized and generated Ansible inventory without adding workload policy to
  the PVE schema.

## Impact

- Expected implementation areas: a narrow template-architecture validation and
  generated-hostvar addition in the existing PVE inventory package; a new K3s
  configuration/validation package under `automation/src/iaas_automation/`;
  reusable Ansible roles and playbooks under `automation/ansible/`; explicit root
  command entrypoints; tests; operator documentation; and the reserved
  `platform/` boundary documentation.
- Existing PVE inventory gains only a validated template architecture and derived
  `pve_architecture` Ansible host fact; the K3s resolver consumes it read-only.
- Existing template declarations and committed generated inventory must be
  migrated together so the new required generic fact does not invalidate current
  environments; this is source metadata only and performs no PVE mutation.
- Online preflight is read-only. Deployment, snapshot, and upgrade commands are
  explicit mutations and are never included in the aggregate offline gate.
- Registry endpoints and proxy policy are committed only when non-sensitive;
  credentials remain protected runtime inputs and are never written to CLI
  arguments, generated/cached state, diffs, or review output.
- No PVE apply, guest bootstrap, K3s install, infrastructure access, or external
  state mutation is part of designing this change.
