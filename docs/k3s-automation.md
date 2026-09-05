# K3s automation operator boundary

This page describes the current repository capability and its evidence
boundary. It is deliberately more precise than a platform design document:
the reusable software pieces and their synthetic tests exist, but this change
does not deploy K3s to Astra or qualify a live cluster.

## Current status

The current implementation is a software-only K3s automation foundation. The
following pieces are implemented and reusable:

| Area | Current capability | Evidence boundary |
| --- | --- | --- |
| PVE source and VM handoff | Inventory validation/generation, template-derived `amd64`, OpenTofu VM module, cloud-init artifacts, and generated Ansible facts | Existing PVE workflows; no K3s node is declared in the Astra inventory |
| VM baseline | `vm_baseline` owns common Debian identity, network, packages, and services | A prepared Debian VM is a prerequisite, not evidence of a K3s installation |
| K3s intent | Composes a separate intent YAML with the selected generated PVE inventory and renders a deterministic redacted model | Synthetic fixtures and offline Python tests only |
| K3s host checks | Scoped read-only preflight and bootstrap-verification roles/playbooks | Live checks are operator actions; no live result is implied by syntax or unit tests |
| Controlled deployment | Explicit whole-cluster deployment orchestration: same-invocation preflight, bootstrap server, protected active-token handoff, then serial server/agent joins | Synthetic/static contract evidence only; no guest has been changed by this change |
| Day-two operations | Explicit, source-scoped embedded-etcd snapshot and whole-cluster serial upgrade workflows | Snapshot evidence is node-local software workflow evidence; no restore or retention qualification, and no live upgrade has run |

The implementation must not be described as installed, running, highly
available, production-ready, or Astra-qualified. Passing offline tests proves
contracts and safety boundaries, not guest reachability, network health, API
readiness, etcd quorum, or workload readiness.

Synthetic fixtures are the only K3s node data committed by this capability.

## Source-inventory generation branches and prepared VM handoff

The source-of-truth path has two branches after the same validated inventory:

```text
environments/astra/inventory/pve-cluster.yml
environments/astra/inventory/vms.yml
                    |
                    v
          PVE inventory validation and normalization
                    |
        +-----------+------------+
        |                        |
        v                        v
 generated OpenTofu input       generated Ansible inventory
        |                        |
        v                        v
 template-derived full clone    VM-owned host facts
        |                        |
        v                        |
 cloud-init user/network data   |
        |                        |
        +-----------+------------+
                    v
              prepared Debian VM
                    |
                    v
                vm_baseline
                    |
                    v
              K3s host handoff
```

`pve-cluster.yml` owns PVE topology, networks, templates, and placement policy;
`vms.yml` owns VM lifecycle declarations. Validation derives the canonical
`pve_architecture` fact from the referenced template and emits the generated
OpenTofu and Ansible inputs under `environments/astra/generated/`. A K3s
overlay does not add K3s fields to either source inventory or copy VM facts.

The OpenTofu PVE module performs the template-derived VM clone. This is the
template-clone/cloud-init handoff: the cloud-init renderer produces paired
user-data and network-config artifacts. Upload and
verification use the exact rendered artifacts and their manifest/checksum;
cloud-init is therefore the identity/network handoff to a guest, not a K3s
installer. `vm_baseline` remains the owner of common Debian guest policy. K3s
roles consume the resulting host and SSH facts after that baseline is
available.

## Composed K3s intent and VM facts

The K3s document declares K3s-owned intent only: cluster name and version,
embedded-etcd topology, API endpoint policy, Pod/Service CIDRs, component
policy, artifact map, registry policy, service-proxy lifecycle, snapshot source,
token reference, and node role/bootstrap markers. A node entry is intentionally
small:

```yaml
nodes:
  - vm_ref: synthetic-server-01
    role: server
    bootstrap: true
```

The resolver reads `vm_ref` from the explicitly selected generated inventory.
It obtains `ansible_host`, canonical architecture, and the unique NIC whose
generic role is the declared cluster node-network role. Node IP, prefix,
subnet, and the operating-system interface observed during preflight remain
VM/runtime facts. The overlay cannot override them or silently fall back to a
storage or ingress NIC.

The composed model validates one or an odd number of at least three embedded-
etcd servers, exactly one bootstrap server, unique derived node addresses,
non-overlapping cluster CIDRs, endpoint/TLS-SAN policy, architecture coverage,
and external-reference-only secrets. `k3s-check` validates this model and
`k3s-render` writes its deterministic non-secret review form.

Fixtures under `tests/fixtures/k3s/` use synthetic names and documentation
addresses. They are not an inventory of Astra nodes and must not be replaced
with copied per-node production facts.

## Artifact acquisition and registry/proxy policy

K3s artifacts are selected by the architecture inherited from the VM facts.
Each selected artifact is pinned to the exact declared K3s version and carries
an HTTPS URL and SHA-256 checksum. The acquisition role uses the same-path
selected artifact endpoint and action-scoped proxy/authentication inputs that
preflight is expected to check; it does not execute an unpinned remote
installer. Artifact
credentials are runtime inputs, not values in intent, generated output, or
command arguments.

The K3s runtime role owns only K3s/containerd files (registry fallback/TLS and
service-proxy retirement):

- `registries.yaml` is rendered from validated HTTPS mirrors, rewrite rules,
  TLS references, authentication references, and explicit upstream fallback
  policy;
- fallback denial is represented by the supported K3s setting for the
  declared version, so a failed mirror cannot silently use the default
  upstream endpoint;
- K3s and K3s-agent service proxy environments are rendered before a service
  start; `NO_PROXY` is derived from loopback, node networks and addresses,
  Pod/Service CIDRs, cluster domain, API endpoint, and registry endpoints;
- bounded explicit additions are allowed, while broad bypasses are rejected;
  retiring policy removes only files owned by this role and then follows the
  controlled restart boundary.

This is not a generic proxy manager. This is the separate APT/shell/Git boundary:
Debian APT sources, APT proxy settings,
system trust-anchor policy, and global shell or Git proxy settings remain a
separate VM-baseline/environment-policy specification. K3s preflight may
inspect configured APT-source reachability and the selected artifact/registry
path; it does not run `apt update`, rewrite APT configuration, or change global
shell/Git settings.

## Protected secret injection

Committed YAML stores references such as `op://vault/item/field`, never a
token, password, private key, certificate body, or proxy credential. Online
wrappers require an explicit overlay, generated inventory, non-empty scope, and
the action-scoped protected runtime secret file when that action needs secrets.
The current protected JSON channel requires a regular file with restrictive
permissions and resolves only exact external references.

Resolved values stay out of CLI arguments, generated or cached state, Ansible
facts/fact cache, diffs, ordinary controller temporary files, and logs. The
shared lookup accepts only the protected file path plus an external reference;
it is consumed directly by `no_log` role tasks. Node-side runtime files are
role-owned, redacted/no-diff, and restrictive in mode. The stable server-token
reference remains part of the stable intent and supplies only bootstrap: after the bootstrap API is healthy, the
workflow reads `/var/lib/rancher/k3s/server/token` through a `no_log` ephemeral
result, validates its credential portion (and CA hash when the external input
is already secure), then uses that active secure token for later joins. It is
not added to inventory, facts, a controller file, or ordinary output.

## Snapshot and upgrade boundary

The composed model accepts exactly one declared server as the snapshot source
and derives the root-only node-local directory
`/var/lib/rancher/k3s/server/db/snapshots`. The reusable
`automation/ansible/playbooks/k3s/snapshot.yml` workflow requires an explicit
scope containing exactly that source server, checks API, embedded-etcd, and
service health, creates a deterministic node-local snapshot, and reports only
non-sensitive metadata. This is a software workflow and does not prove a
recoverable backup. It does not copy to the controller/repository, perform
automatic retention or deletion, or make a restore-readiness claim.

The offline upgrade planner validates an explicit whole-cluster scope, rejects
downgrades, skipped minors, unsupported mixed versions, and nodes above the
target, and orders pending servers before agents. `k3s-upgrade` consumes that
rendered plan, reruns same-scope preflight, creates the configured local
snapshot, health-checks exact-target nodes before skipping them, and upgrades
remaining servers then agents one at a time. A failed health, stop, download,
start, or post-check halts the workflow. This is still synthetic implementation
evidence, not evidence of a completed live upgrade.

## External-CNI intermediate state

The first-version boundary allows the K3s bootstrap contract to describe an
external CNI/component policy, but does not install Cilium or another CNI.
Bootstrap-level verification may therefore identify the expected
`CNI-not-initialized` intermediate state. It must still block on API failure,
etcd failure, service failure, disk pressure, or any unexpected readiness
failure. Bootstrap evidence is not complete node readiness, workload
networking, ingress, storage, HA, or production qualification.

Cilium, Flux, CSI, Gateway, application resources, and day-to-day application
GitOps remain later platform/application work. No Astra composition or runtime environment secret is added by this capability.

## Command safety classes

Use explicit paths; do not rely on an implicit default overlay or inventory.
The supported K3s facade currently exposes these classes:

| Class | Entry points | Effect |
| --- | --- | --- |
| Offline-safe | `make k3s-check`, `make k3s-render`, `make k3s-ansible-syntax`, `make k3s-ansible-lint` | Validate/render synthetic or selected files; no host access |
| Online read-only | `make k3s-preflight`, `make k3s-verify` | Require an explicit scope; preflight additionally requires protected runtime inputs when the selected paths are authenticated |
| Mutation-capable | `make k3s-deploy`, `make k3s-snapshot`, `make k3s-upgrade` | Bind explicit files/scope; deploy and upgrade require protected runtime inputs and rerun preflight before mutation; never included in aggregate `make check` |

`make check` remains an offline repository gate. A command being syntactically
valid, or a role being reusable, does not authorize an online action. Each
implemented mutation entry point binds one validated model to one explicit
scope and performs its required read-only safety gate before mutation.

The first version intentionally has no K3s command surface for automatic
restore, snapshot retention/deletion, uninstall, datastore replacement, or
destructive node removal. Those operations must not be inferred from the
snapshot playbook, snapshot path, PVE lifecycle commands, or a role's
file-retirement capability.

## Software-only acceptance boundary and future recovery design

Acceptance for this change consists of synthetic Python tests, Ansible syntax
and static contract tests, deterministic redacted rendering, protected-secret
channel tests, and explicit safety-boundary checks. It does not require PVE
apply, guest bootstrap, K3s installation, a live API, or Astra nodes.

Recovery is intentionally a separate future design. Before any recovery
implementation is accepted, it needs an explicit backup destination and
transport, retention/deletion authority, encryption and access control, token
and CA handling, restore validation in an isolated target, node replacement and
quorum rules, operator approval, and a tested rollback/abort path. Until that
design exists, snapshot creation and the current software evidence must not be
presented as recoverability or disaster-recovery qualification.
