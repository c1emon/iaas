## Context

See `proposal.md` for motivation. The current repository already provides the
lower half of the required flow. Source VM inventory is validated once and
generates two sibling outputs; the Ansible inventory is not produced by
cloud-init:

```text
vms.yml -> validate and normalize
        |-> generated OpenTofu tfvars -> template full clone + cloud-init -> prepared VM
        `-> generated Ansible inventory

prepared VM + generated Ansible inventory -> common Debian VM baseline
```

The generic VM model supports deterministic multi-NIC cloud-init guests and the
foundation model records future K3s recovery dependencies. No K3s configuration
schema, roles, playbooks, command surface, or live nodes exist. Earlier GitNexus
analysis reported `validate_vms` as a CRITICAL upstream hub across
generation, health, and preflight, so the K3s contract must not be added to that
generic validator.

The core flow is also recorded in `k3s-automation-core-flow.drawio`.

## Goals / Non-Goals

**Goals:**

- Add a reusable K3s overlay that composes with existing VM-derived Ansible host
  facts without duplicating their architecture, IP, or infrastructure data.
- Support Debian K3s host preflight, pinned deployment, bootstrap verification,
  embedded-etcd snapshots, and controlled upgrades.
- Support explicit K3s/containerd registry mirrors and K3s service proxy policy
  without turning K3s automation into a generic workstation proxy manager.
- Make every online or mutation-capable action explicit, scoped, and fail-closed.
- Allow complete software-level acceptance with synthetic fixtures and no live
  environment.

**Non-Goals:**

- Adding K3s nodes or network values to `environments/astra/`.
- Running PVE apply, VM bootstrap, K3s deployment, snapshot, or upgrade.
- Installing Cilium, Flux, CSI, Gateway, applications, or DNS integration.
- Supporting kubeadm, NixOS, Talos, or multiple Kubernetes distributions through
  a common abstraction.
- Supporting SQLite or an external K3s datastore in the first version.
- Configuring Debian APT sources/proxies or global shell/Git proxy settings.
- Automating restore, uninstall, destructive node removal, or production
  qualification.

## Current State and Gap Analysis

| Layer | Current state | Gap addressed by this change |
| --- | --- | --- |
| PVE template and clone | Implemented | Reused unchanged |
| cloud-init identity and multi-NIC | Implemented | Reused unchanged |
| generated Ansible host facts | Implemented without architecture | Add template-derived `pve_architecture`, then compose it with K3s intent |
| common Debian VM baseline | Implemented | Required predecessor for K3s roles |
| Debian package-source and general proxy policy | Not implemented | Validate required access only; defer generic configuration |
| foundation recovery metadata | Implemented offline | Not treated as proof that services are live |
| K3s topology contract | Missing | Add composed, independently validated K3s overlay |
| K3s host preflight | Missing | Add online read-only workflow |
| K3s server/agent deployment | Missing | Add explicit mutation workflow |
| K3s registry and service-proxy policy | Missing | Add K3s-owned runtime configuration |
| bootstrap verification | Missing | Add read-only, stage-qualified checks |
| snapshot and upgrade | Missing | Add bounded Day-2 workflows |
| CNI/GitOps/storage/ingress | Design direction only | Defer to later platform changes |
| live cluster evidence | None | Remains intentionally absent |

The existing design checklist is stale for the first four rows above. This
change should update current documentation when implemented, but historical
OpenSpec archives remain unchanged.

## Decisions

### Compose VM facts with a separate K3s intent overlay

The K3s overlay references host names from an explicitly selected generated
Ansible inventory and selects one generic VM NIC role for node identity across
the cluster. The resolver obtains the CPU architecture and SSH address from the
generated host facts, then obtains node IP, prefix, and NIC network from the
unique `pve_nics` entry with that role. Architecture is declared once on the referenced VM template,
inherited by normalized VMs, and rendered as `pve_architecture`. The overlay
declares only K3s-owned intent: cluster policy, architecture-keyed artifact map,
node-network role, node role, and bootstrap marker. Per-node architecture, IP addresses, network
interfaces, gateway, DNS, VM resources, template, and PVE placement are not
repeated or overridden in the K3s document.

```yaml
node_network_role: cluster
nodes:
  - vm_ref: synthetic-k3s-server-01
    role: server
    bootstrap: true
```

The example intentionally contains no IP or interface. The node address is the
address of the VM NIC whose generic role is `cluster`; `ansible_host` remains the
independently VM-selected SSH address. Online preflight discovers the guest
interface that owns the node IP; its operating-system interface name is runtime
evidence, not K3s configuration. The first version requires one cluster-wide
role and permits no per-node override or automatic fallback. An early lab may
explicitly select `management`, but storage and ingress roles remain invalid for
node identity.

The composed model fails if a host is missing or ambiguous, if its connection NIC
or selected node-role NIC is missing, ambiguous, or unusable, if the template
architecture is unusable, if no pinned artifact is
declared for a derived architecture, or if manually duplicated VM facts are
supplied. The only generic VM-contract addition is the template-derived
architecture host fact; no K3s-only field enters `vms.yml`. Implementation must
run impact analysis before the narrow validator/renderer change because earlier
graph analysis identified those paths as high-risk shared boundaries.

Alternative considered: add K3s roles and cluster values directly to the PVE VM
schema, or manually copy VM IPs into the K3s overlay. Rejected because either
couples cluster lifecycle to VM provisioning or creates two sources of truth.

### Use Debian plus Ansible and keep K3s out of the template

The existing Debian genericcloud template remains minimal. cloud-init provides
identity, SSH, and network reachability; `vm_baseline` converges the common OS;
K3s-specific roles then manage prerequisites and K3s.

Alternative considered: bake K3s into the VM template or switch to NixOS/Talos.
Rejected for this capability because it would bind cluster versions and node
identity to image lifecycle or replace the existing host-management model.

### Introduce one small configuration validator, not a platform framework

The K3s contract contains only the inputs needed for safe automation:

- cluster name and exact K3s version;
- one architecture-keyed pinned artifact source/checksum map with
  action-scoped acquisition proxy/authentication references;
- embedded-etcd policy;
- API endpoint mode: derived from the bootstrap server, or one explicit stable
  external DNS/VIP whose required TLS SAN is derived automatically;
- Pod and Service CIDRs;
- external-CNI policy and a separate packaged-component disable policy;
- registry mirrors, rewrite/fallback policy, and K3s service-proxy references;
- runtime secret references;
- one node-network role plus node host reference, role, and bootstrap marker;
- snapshot source and upgrade safety policy.

The validator loads the K3s document and the selected generated Ansible
inventory, composes K3s intent with VM facts, and produces a deterministic
redacted review view. It validates unique derived node IPs; valid, non-overlapping
Pod and Service CIDRs; no overlap with the selected hosts' VM subnets; endpoint
derivation; and server-wide values that K3s requires to match. A fixed endpoint
must be an external stable DNS/VIP rather than a repeated selected-node address,
and the renderer adds it to required TLS SANs. It
does not generate PVE resources, discover hosts dynamically, or permit the K3s
overlay to override VM facts.

Alternative considered: build a generic Kubernetes distribution schema for both
K3s and kubeadm. Rejected because there is only one confirmed consumer and the
two distributions have materially different installation and lifecycle rules.
If a later change adopts full Kubernetes, it can reuse the VM facts, baseline,
secret, registry, and platform boundaries; the K3s-specific install, datastore,
snapshot, and upgrade workflows are the parts that must be replaced.

### Bound the first datastore to embedded etcd

The first version supports embedded etcd only. It accepts either one server or
an odd number of at least three servers, requires exactly one explicit initial
server, renders `cluster-init` only there, and joins every additional server to
the resolved registration endpoint. SQLite and external datastores are rejected
before host access so bootstrap and backup do not acquire multiple meanings.

The cluster policy retains a stable external reference to the server token used
to encrypt datastore bootstrap data. For the default self-signed CA bootstrap,
that reference may
resolve to the short credential token accepted by the initial server. After the
initial server starts, the workflow reads its active secure token through the
protected ephemeral channel; it compares credential portions, validates the CA
hash whenever the external token is already secure, and uses the active secure
token for all later server and agent joins. The snapshot policy names exactly
one declared server as its source. Snapshot creation checks server and embedded-
etcd health but does not depend on resolving or comparing the external token.
Snapshot files stay on that server by default in a root-only location; ordinary
output contains only non-sensitive identity, location class, and outcome.
Fetching a snapshot or token to the controller or repository is not part of this
capability, and snapshot creation alone does not claim restore readiness.

The first version does not delete snapshots automatically. Retention and restore
qualification require a later change with an explicit storage and recovery
policy.

### Separate host package access from K3s runtime egress

Debian APT sources, APT proxy configuration, system trust anchors, and optional
global shell or Git proxy settings are generic guest policy. They remain owned by
`vm_baseline` and an explicitly selected environment policy-vars file. They
require a separate baseline change because they also affect ordinary VMs. This
change only makes K3s
preflight inspect the configured package sources and test the DNS, TCP, and TLS
reachability needed for declared packages and pinned K3s artifacts without
running `apt update` or changing the host.

Each node architecture comes from its generated `pve_architecture` VM fact. The
overlay contains no per-node architecture field; it declares an artifact map
keyed by supported normalized architectures. Every derived architecture must
resolve to an exact K3s artifact source and checksum for the pinned version.
The first implementation supports canonical `amd64`; guest fact `x86_64`
normalizes to it, while canonical `amd64` remains unchanged. Additional template
architectures require a later change with corresponding artifacts and tests.
Preflight normalizes the guest-reported value before requiring an exact match
with the generated VM fact.
Artifact preflight and acquisition use the same resolved URL and the same
action-scoped proxy/authentication references. These credentials are never
promoted to global shell state. If authenticated validation or acquisition is
declared, standalone preflight requires the corresponding read-only runtime
secret; missing secrets fail before host mutation.

The K3s overlay does own runtime-specific egress policy:

- container registry mirrors and optional rewrites;
- an explicit allow/deny decision for fallback to upstream registry endpoints;
- verified non-secret CA artifacts and runtime references for registry
  authentication or client TLS material;
- runtime references for K3s/containerd HTTP proxy credentials and explicit
  extra bypass destinations.

Fallback denial renders the version-supported
`disable-default-registry-endpoint` K3s setting in addition to
`registries.yaml`; a denied mirror failure must not contact the default upstream
endpoint. Registry endpoints require HTTPS with certificate verification. CA
artifacts carry an exact SHA-256 identity, and every referenced CA/client-cert
path and permission is checked before service mutation; insecure registries and
TLS-skip settings are rejected.

The composed model derives `NO_PROXY` entries from localhost/loopback, every
declared node subnet, the Pod and Service CIDRs, configured cluster domain, API
endpoint, and internal registry endpoint, then adds bounded, validated
operator-supplied extras. Global bypasses such as `/0` are rejected. The K3s role writes
`/etc/rancher/k3s/registries.yaml` and the server/agent systemd environment before
the service first starts. Sensitive rendered files are root-only and task output
is redacted. A later policy change or explicit retirement removes only role-owned
files and uses the controlled serial restart path, verifying each node before
continuing; unchanged policy causes no restart. It never configures an
interactive shell or system-wide Git client.

### Split workflows by safety class

The command surface follows the repository's existing safety model:

```text
offline-safe:       k3s-check, k3s-render, k3s-ansible-syntax
online read-only:   k3s-preflight, k3s-verify
explicit mutation:  k3s-deploy, k3s-snapshot, k3s-upgrade
out of scope:       k3s-restore, k3s-uninstall, destructive node removal
```

All commands require explicit K3s configuration and Ansible inventory paths.
Every online command additionally requires a non-empty explicit host scope, and
online commands require any runtime secrets needed to exercise their declared
read-only or mutation path. There is no
implicit inventory-wide default; an operator may explicitly choose all declared
K3s nodes. A partial deployment scope is never silently expanded: omitted
prerequisite nodes must pass live read-only verification in the same invocation
or the command fails before mutation. No K3s mutation target is added to the
aggregate `make check` gate.

Alternative considered: one playbook with tags for every operation. Rejected
because tag selection makes safety boundaries and failure ordering harder to
review.

### Use ordered Ansible phases

Reusable roles remain narrow while playbooks own orchestration:

```text
k3s_preflight (read-only)
  -> k3s_prerequisites
  -> initial server
  -> additional servers
  -> agents
  -> k3s_verify (read-only)
```

Deployment stops when a prerequisite, bootstrap, or join phase fails. The
initial server is selected explicitly rather than inferred from inventory order.
The mutation command reruns preflight in the same invocation against the same
resolved configuration, inventory, and scope. Server `node-ip` and
`advertise-address` come from the VM NIC selected by the cluster-wide node-network
role. A fixed external
registration endpoint is added to the rendered TLS SANs automatically. K3s executable artifacts are pinned and
integrity-verified; unpinned remote installer content is not executed.

### Treat external-CNI bootstrap as an intermediate state

The chosen platform direction uses Cilium later. Core K3s automation therefore
models two explicit policy axes: external-CNI settings disable Flannel and the
packaged network-policy controller, while packaged-component settings disable
Traefik and ServiceLB. This change verifies API availability, registration,
versions, and services, but does not require or claim complete Node readiness
before the Cilium change. Only the expected CNI-not-initialized condition may be
classified as bootstrap-ready; disk pressure, kubelet failure, unexpected
service failure, and other readiness causes remain blocking failures.

Alternative considered: temporarily deploy Flannel and replace it later.
Rejected because that creates an unnecessary in-place CNI migration path.

### Inject secrets only at execution time

Committed K3s configuration contains external references, not token values. The
server-token reference is stable; changing its resolved value requires a
separately reviewed token-rotation operation outside this capability. Runtime
injection uses a documented protected channel and does not add resolved
values to CLI arguments, generated or cached state, Ansible facts/fact cache,
diffs, or ordinary controller temporary files. Logs and registered Ansible
results use redaction and no-diff behavior; protected temporary material is
permission-restricted and removed after the action. Any node-side secret files
use restrictive permissions. Redaction tests exercise every command class, not
only static secret scans. Embedded-etcd snapshots are treated as sensitive
artifacts even though their reported metadata is non-sensitive.

The active secure join token obtained after initial bootstrap is ephemeral
controller memory only: it is never written to inventory, facts/fact cache,
arguments, controller disk, or ordinary output, and it is discarded after the
invocation.

Alternative considered: generate a committed or cached inventory containing the
join token. Rejected because it expands plaintext secret exposure and recovery
risk.

### Bound first-version Day-2 operations

The first capability includes read-only verification, embedded-etcd snapshot,
and a serial controlled upgrade because they are required to operate what
deployment creates. An upgrade target must be exact and no lower than any
observed node version. A node below the target may advance within its current
Kubernetes minor or by exactly one minor; downgrade, skipped-minor, or unsupported
mixed-version states fail before mutation.

Upgrade reruns preflight and creates a successful pre-upgrade snapshot in the
same invocation, using the same resolved cluster, inventory, and explicit scope.
The first version accepts only an explicit whole-cluster upgrade scope. It
upgrades one server at a time before upgrading agents one at a time, verifies API
and etcd health after each server, verifies registration and service state after
each agent, and stops at the first failed stage. A retry with the same target is
resumable: nodes already at the target are health-verified and skipped, while
eligible lower-version nodes continue in the same server-then-agent order.

Automatic restore, uninstall, and destructive membership changes remain outside
scope because they need separate rollback, data-loss, and quorum design. The
first command surface exposes no entrypoint for them; operator documentation
points to a future separately reviewed recovery design instead of simulating a
runtime refusal path.

## Risks / Trade-offs

- [No real K3s runtime is exercised] -> Label acceptance as software-only and
  require a later environment deployment change for live evidence.
- [A selected VM has no usable NIC for the declared node-network role] -> Fail closed during composition;
  do not accept a copied IP or guess another VM interface.
- [External CNI leaves an intentionally incomplete cluster stage] -> Define
  bootstrap-ready checks separately from complete platform readiness.
- [APT or artifact access is unavailable] -> Report the exact endpoint and fail
  read-only preflight; do not mutate generic package-source policy from K3s.
- [Proxy bypass omits cluster-local traffic] -> Derive node, Pod, Service, API,
  and registry destinations from the composed model and reject unsafe overrides.
- [A registry mirror silently falls back upstream] -> Require an explicit
  fallback decision, render the K3s default-endpoint-disable setting when denied,
  and test that mirror failure does not reach upstream.
- [Artifact preflight and download use different egress paths] -> Resolve one
  pinned source and action-scoped proxy/auth path for both operations.
- [K3s version changes alter flags or packaged-component behavior] -> Pin the
  version and checksum, test rendered configuration, and update through a
  reviewed change.
- [Snapshots expose secrets or are mistaken for recoverability] -> Keep them
  root-only and node-local by default, report metadata only, perform no automatic
  deletion, and do not claim restore readiness until a separate restore drill
  exists.
- [An interrupted upgrade cannot be resumed] -> Accept only the supported
  old/target mixed state, verify and skip target-version nodes, and continue the
  remaining serial stages.
- [Future kubeadm adoption duplicates work] -> Preserve the VM, host inventory,
  secret, and platform boundaries, but do not build a speculative distribution
  abstraction now.

## Migration Plan

1. Add the generic template-derived VM architecture fact, migrate each existing
   template declaration to its evidenced canonical architecture, regenerate the
   Ansible hostvar, then add the compositional K3s overlay contract and synthetic
   VM/K3s fixtures. This changes source metadata only and performs no PVE apply.
2. Add offline validation/rendering, including artifact, registry and
   service-proxy policy, and safety-class command entrypoints.
3. Add read-only host, package-source, same-path artifact, authenticated registry,
   and TLS preflight.
4. Add ordered Debian K3s prerequisite, runtime-registry/proxy, server, and agent
   deployment roles.
5. Add node-local snapshot and resumable controlled-upgrade workflows.
6. Complete software-only validation and archive this capability change without
   adding an Astra K3s configuration.
7. Use a separate future OpenSpec change to declare actual nodes and perform the
   first live deployment, followed by separate Cilium and platform changes.

Rollback during this capability-only change is ordinary source reversion because
no external state is created. Rollback rules for a future live deployment must
be defined by that environment change before it applies the capability.
