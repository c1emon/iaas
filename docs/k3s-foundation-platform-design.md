# K3s application platform and foundation services design

这是架构设计而非操作手册。当前可执行操作、参数、证据边界与未实现项以
[《Astra 基础设施操作手册》](operations/README.md) 为准。

This document records the current design direction for the future application
platform and the external foundation services that support it. It is an
architecture design note, not an implementation plan.

## Purpose

The repository currently manages IaaS infrastructure around Proxmox VE,
TrueNAS SCALE, OPNsense, switches, Ansible, OpenTofu, and Docker-based
services. Existing applications run on about five Docker hosts across a mix of
VMs and bare-metal machines.

The target direction is to introduce a K3s-based application platform while
keeping critical bootstrap services outside the cluster. The design goal is to
support:

- automatic workload placement;
- automatic cross-host rescheduling where storage semantics allow it;
- volume attach/detach through Kubernetes storage primitives;
- health-aware rollout and rollback;
- a unified Gateway/Ingress layer;
- controlled internal DNS automation;
- clear recovery paths for the services required before the cluster can be
  recovered.

## Chosen architecture

### Application platform

The application platform direction is:

```text
K3s
├─ Cilium
├─ Gateway API
├─ Cilium Gateway first, Traefik as fallback/comparison
├─ TrueNAS official CSI first for PoC, democratic-csi as fallback
├─ local-path for cache/tmp/preview/transcode data
└─ Flux GitOps
```

K3s is the application orchestration layer. Proxmox VE remains the VM lifecycle
layer, TrueNAS remains the storage platform, and OPNsense remains the network
edge and firewall authority.

### K3s node placement and operating system

The first K3s implementation should use virtual-machine nodes rather than
bare-metal nodes. K3s VMs should be distributed across different Proxmox VE
nodes where available, but if the available PVE nodes do not provide three
independent physical failure domains the cluster must still be documented as
recovery-backed rather than true quorum HA.

Phase one K3s nodes should use Debian cloud images with cloud-init and Ansible
bootstrap. NixOS, Talos Linux, Flatcar, Fedora CoreOS, or other atomic node
operating systems are not adopted in phase one. The platform relies on
reproducible OpenTofu VM creation, cloud-init network initialization, Ansible
idempotent host bootstrap, pinned K3s versions, PVE snapshots, K3s/etcd
backups, and Flux recovery procedures for rollback and rebuild.

Atomic or immutable node operating systems may be revisited later only after the
VM, multi-NIC, K3s, Cilium, Flux, and storage paths are stable and OS drift or
node upgrade rollback becomes a real operational problem.

### K3s node network model

K3s VMs may use multiple NICs in phase one. Each NIC must have a single clear
responsibility, and K3s must not rely on automatic interface selection.

The target network model is:

```text
K3s VM
├─ mgmt0
│  ├─ SSH / Ansible / kubeconfig management access
│  ├─ default route and internet access
│  ├─ OS package updates and image pulls
│  └─ default Pod egress path unless a later Cilium egress policy overrides it
├─ cluster0
│  ├─ K3s node-ip and server advertise-address
│  ├─ K3s server/agent and etcd peer communication
│  ├─ Cilium node-to-node underlay
│  └─ isolated L2 network with no default gateway
├─ storage0
│  ├─ TrueNAS CSI data path
│  ├─ NFS / iSCSI / future storage transport access
│  └─ storage VLAN with no default gateway
└─ ingress0
   ├─ Cilium Gateway entrypoints
   ├─ LoadBalancer / VIP announcement
   ├─ externally reachable service access
   └─ not used for K3s node identity or Cilium node-to-node underlay
```

The `mgmt0` interface is the only phase-one default-route owner. `cluster0`,
`storage0`, and `ingress0` should not receive default gateways unless a later
design explicitly introduces policy routing or dedicated egress behavior.

K3s node identity must be explicit:

```yaml
node-ip: <cluster0-ip>
advertise-address: <cluster0-ip>
```

`node-ip` is the Kubernetes InternalIP for the node. It should not be assigned
from the storage or ingress network. If a dedicated `cluster0` network is not
available during an early lab phase, the management IP may be used temporarily,
but storage and ingress IPs must still be excluded from node identity.

Cilium depends on a working underlay network. It is responsible for Pod,
Service, policy, Gateway, LoadBalancer, and optional egress-network behavior; it
is not responsible for making K3s node underlay connectivity work. K3s
server/agent connectivity, kubelet-to-apiserver connectivity, etcd peer traffic,
node access to Harbor/DNS/TrueNAS, VLANs, routes, and firewall rules must work
before Cilium is installed.

The ingress/service NIC is dedicated to externally reachable service entrypoints,
including Cilium Gateway and LoadBalancer/VIP advertisement. It is not the K3s
node identity network and is not used for Cilium node-to-node underlay traffic
in phase one.

Cloud-init should configure multi-NIC VM networking using deterministic MAC
addresses from OpenTofu and `network-config` MAC matching. Interface names such
as `mgmt0`, `cluster0`, `storage0`, and `ingress0` should be assigned with
`match.macaddress` and `set-name`. The current VM automation must be extended
before this target model can be fully provisioned.

### Repository boundaries

K3s-related automation should be split by responsibility rather than placed in a
single catch-all GitOps tree.

The target is an explicit three-way ownership model. This IaaS repository owns
the infrastructure and K3s handoff boundary:

```text
iaas repository
├─ Proxmox / OpenTofu infrastructure
├─ Ansible host and foundation automation
├─ OPNsense and switch automation
├─ foundation service recovery model
├─ K3s node bootstrap
├─ same-model K3s readiness verification
├─ non-secret platform handoff bundle
└─ disaster recovery runbooks
```

Shared in-cluster platform desired state belongs to an independently operated
external platform repository:

```text
external platform repository
├─ Cilium and cluster networking policy
├─ Gateway and ingress platform services
├─ TrueNAS CSI / StorageClass baseline
├─ Flux bootstrap and reconciliation roots
├─ certificates and observability
└─ shared platform recovery procedures
```

Ordinary application releases belong to application repositories:

```text
application repositories
├─ cluster application overlays
├─ HelmRelease / Kustomization definitions for applications
├─ application values and runtime configuration references
├─ application Gateway/HTTPRoute resources
├─ application upgrade PRs
└─ application rollback history
```

Flux may read from both repositories:

```text
Flux
├─ source: external platform repository
│  └─ shared cluster platform desired state
└─ source: application repositories
   └─ application workloads and day-to-day app releases
```

The `platform/` directory in this repository only documents the handoff
boundary. It is not a platform implementation root, and this repository does
not retain compatibility aliases for one. The IaaS workflow does not invoke the
external platform pipeline or claim that handoff has completed. The long-term
rule is:

```text
IaaS infrastructure and K3s lifecycle belong here;
shared in-cluster platform desired state belongs in the external platform repo;
ordinary application deployment and upgrades belong in application repos.
```

### Foundation plane

The foundation services remain outside K3s long-term:

```text
Foundation plane
├─ OPNsense / gateway
├─ TrueNAS SCALE
├─ internal DNS
├─ sing-box / proxy
├─ Harbor
├─ external databases
└─ Authentik
```

These services are managed as recovery-critical infrastructure rather than as
ordinary application workloads. They are not scheduled by K3s.

The foundation management model is:

```text
repo-led configuration
  + emergency exceptions
  + Ansible execution
  + Docker Compose for multi-container services
  + systemd for native services such as sing-box
  + 1Password secret injection
```

## Confirmed decisions

### Minimum startup set

Before recovering K3s or upper-layer applications, these services must be
available:

1. OPNsense / gateway
2. TrueNAS
3. internal DNS
4. sing-box / proxy
5. Harbor
6. external databases

Authentik and Git/secrets are not hard prerequisites for starting K3s recovery,
but they still need independent recovery paths.

### Recovery order

The preferred recovery order is:

```text
OPNsense
  ↓
TrueNAS
  ↓
internal DNS
  ↓
sing-box / proxy
  ↓
Harbor
  ↓
external databases
  ↓
K3s / upper-layer applications
```

### DNS

Internal DNS is a hard foundation dependency, but the first phase does not add
DNS redundancy. The immediate target is health checking and a recovery runbook.

Internal application DNS records may be maintained automatically by
GitOps/ExternalDNS. Public or edge DNS changes still require manual approval.

### Harbor

Harbor remains a hard foundation dependency. The fallback strategy is to
pre-pull critical images onto nodes rather than relying on upstream registry
fallback by default.

Critical images should include, at minimum, the images required to recover core
K3s components, Cilium, Gateway, CSI, Flux, and other cluster bootstrap
components.

### Authentik and break-glass access

Authentik is not a prerequisite for K3s recovery. Critical systems must retain
local administrator accounts or emergency tokens so that SSO failure does not
block recovery.

### Configuration source of truth

Foundation configuration is repo-led with emergency exceptions:

- routine changes go through the repository and Ansible;
- direct host or UI changes are allowed during incidents;
- emergency changes must be written back to the repository afterward.

UI access for Harbor, Authentik, DNS, or similar tools is allowed for emergency
changes, but should not become the normal configuration source of truth.

### Secrets

Foundation secrets are injected through 1Password. The repository should store
secret references and deployment wiring, not decrypted secret values.

### Backups and restore drills

Foundation services require regular backups and quarterly restore drills for
critical services.

Backups alone are not considered sufficient unless restoration has been tested.

### Upgrade strategy

Foundation services use notify-then-manual upgrades. Tools such as DIUN or
Renovate may notify or open PRs, but Harbor, Authentik, DNS, sing-box, and other
foundation services should not auto-upgrade.

### OPNsense boundary

OPNsense should expose a small number of stable Gateway/VIP entrypoints. K3s
handles service-level routing behind those entrypoints.

The first design target is not per-service dynamic OPNsense firewall or DNAT
rule creation.

### Foundation service placement

Foundation services stay outside K3s long-term. They are managed by the
foundation plane rather than migrated into the application cluster.

### Storage plugin selection

The official TrueNAS CSI driver is the first PoC candidate. If it passes
validation, it becomes the preferred production default. democratic-csi remains
the explicit fallback.

StorageClass names should be abstract enough that the backend can change later,
for example:

```text
shared-rwx
block-rwo
cache-local
```

### K3s control-plane HA

The first phase accepts non-true HA. If three K3s server instances are deployed
across fewer than three independent physical failure domains, the system must be
documented as recovery-backed rather than true quorum HA.

### Storage network scope

Only VM-based K3s nodes should connect to the storage VLAN in the first phase.
Bare-metal K3s nodes should not host workloads that require block storage or
storage VLAN access.

The storage VLAN is a storage data-plane network, not a general application or
management network. K3s VM `storage0` interfaces may access the TrueNAS storage
endpoint; ordinary LAN clients, bare-metal K3s nodes, and ingress/service
networks should not be given storage VLAN access in phase one.

The TrueNAS CSI endpoint used by K3s must use the storage VLAN address. The
Linux route to that endpoint should be a connected or explicit storage route via
`storage0`, not the node default route. Ordinary Pod egress continues to use the
node default route on `mgmt0` unless a later Cilium Egress Gateway or policy
routing design overrides it.

### Gateway implementation

Cilium Gateway is the first implementation candidate. Traefik remains the
fallback and comparison point.

Only one Gateway implementation should own a production hostname/VIP set at a
time.

Gateway and LoadBalancer VIPs should be announced on the ingress/service network
in phase one. The ingress/service network is externally reachable by clients,
OPNsense, reverse proxies, or other approved service consumers. It should not be
used as the K3s node identity network or as the Cilium node-to-node underlay.

### GitOps

Flux is the GitOps controller choice for the external platform repository.

The external platform repository's Flux workflow must not depend on Authentik
login to recover the cluster. Its kubeconfig, Flux bootstrap material, age
keys, and required manifests need an offline recovery path.

### Foundation inventory scope

The first foundation inventory should model services as recovery units. It
should cover:

- host;
- service;
- runtime;
- dependencies;
- health check;
- backup;
- restore path;
- break-glass access.

It does not need to cover the full deploy/upgrade/drift lifecycle in the first
iteration.

The committed recovery reference is generated at `environments/astra/generated/docs/foundation-recovery.md`. Offline freshness checks are safe without live infrastructure access (`make foundation-check`), while `make foundation-health` is an explicit online read-only probe path.

### K3s automation route

K3s operational automation should be layered rather than implemented as one
large playbook or one large GitOps tree:

```text
OpenTofu
  → creates PVE VMs, disks, NICs, deterministic MAC addresses, and cloud-init media

cloud-init
  → provides first boot identity, SSH access, initial users, and initial network config

Ansible common VM bootstrap
  → converges ordinary VM baseline: hostname, packages, qemu-guest-agent,
    time sync, SSH/sudo policy, apt configuration, and read-only network validation

Ansible K3s node bootstrap
  → installs K3s host prerequisites, renders /etc/rancher/k3s/config.yaml,
    installs pinned K3s server/agent versions, and performs initial health checks

K3s readiness and platform handoff
  → verifies the declared cluster and emits a non-secret bundle for the external
    platform repository; it does not install or configure shared platform state

External platform repository
  → installs Flux, configures Cilium/Gateway/CSI, and verifies first reconciliation

Application repositories
  → deliver ordinary application resources after the platform repository is ready
```

Cloud-init should not become the long-term host configuration system. It only
needs to make a VM reachable and correctly networked enough for Ansible to
converge it. Ordinary VMs and K3s VMs should share the common VM bootstrap role;
K3s nodes add only the K3s-specific prerequisite and install roles.

The recommended implementation sequence is:

1. add a common Ansible VM bootstrap workflow for existing single-NIC VMs;
2. extend PVE VM inventory, validation, OpenTofu, and cloud-init to support
   multi-NIC cloud-init VMs;
3. add K3s node bootstrap roles and pinned K3s install configuration;
4. add same-model K3s readiness verification and the external platform handoff;
5. have the external platform repository bootstrap Cilium, Flux, CSI, and
   Gateway and validate its first reconciliation;
6. have application repositories deliver ordinary application resources;
7. add Day-2 health, upgrade, backup, and restore-drill commands in the owning
   repository for each layer.

Long-term ownership should remain split:

```text
iaas repository
  → VM lifecycle, K3s bootstrap and readiness, handoff bundle, foundation
    recovery, and IaaS/K3s runbooks

external platform repository
  → Cilium, Gateway, CSI/StorageClasses, Flux, shared platform validation,
    recovery, and platform desired state

application repositories
  → ordinary application workloads, application HelmRelease/Kustomization
    objects, application HTTPRoutes, and day-to-day application upgrades
```

### Foundation health checks

The first health-check layer should cover service-level HTTP/TCP/API checks.
Full end-to-end recovery scenario simulation can come later.

### N100 single point of failure

The first phase accepts N100 as a known single point of failure. No cold standby,
service split, or migration is planned initially. The risk should be recorded
and revisited after the foundation recovery model exists.

## Storage model

The storage model separates data by behavior rather than by application alone.

```text
shared-rwx
  → TrueNAS NFS/RWX
  → shared files, media, uploads, ordinary configuration

block-rwo
  → TrueNAS iSCSI/NVMe-oF/RWO
  → embedded databases and single-writer strong-consistency state

cache-local
  → local-path or equivalent node-local storage
  → cache, tmp, previews, transcoding, rebuildable data
```

Non-embedded databases remain on external dedicated database hosts and are not
part of the K3s persistent-volume design.

JuiceFS remains a supplemental option for existing `datafs`/`confs` use cases,
but it is not the default storage layer for K3s control-plane data, embedded
databases, or GitOps source-of-truth configuration.

### TrueNAS CSI validation scope

The official TrueNAS CSI driver is the first storage implementation candidate,
but it must pass a validation PoC before production workloads rely on it.
`democratic-csi` remains the fallback if the official driver cannot satisfy the
required behavior.

The first PoC should validate at least:

- NFS RWX dynamic provisioning, multi-node mount, reclaim behavior, expansion,
  and node reboot recovery;
- block RWO provisioning, attach/detach, rescheduling to another VM node, stale
  attachment recovery, filesystem resize, and node-failure behavior;
- snapshot and restore behavior where supported by the selected driver and
  backend;
- compatibility with K3s VM nodes that access TrueNAS only through `storage0`;
- failure behavior when a node loses storage VLAN connectivity.

StorageClass names should remain backend-abstract so the CSI implementation can
change without rewriting application manifests:

```text
shared-rwx
block-rwo
cache-local
```

Workloads that require `shared-rwx` or `block-rwo` storage must be scheduled only
on VM-based K3s nodes with storage VLAN access. This may be enforced later with
node labels, taints, affinity, or admission policy. `cache-local` remains for
rebuildable cache, temporary, preview, and transcode data.

## Foundation service management model

Foundation services should be represented as recoverable units rather than only
as applications.

Example conceptual model:

```yaml
foundation_services:
  harbor:
    host: n100
    runtime: compose
    tier: critical
    dependencies:
      - internal_dns
      - external_database
    healthcheck:
      type: https
      endpoint: /api/v2.0/health
    backup_profile: harbor
    restore_runbook: required
    break_glass: local_admin

  sing_box:
    host: rk3588
    runtime: systemd
    tier: critical
    healthcheck:
      type: tcp
    backup_profile: config_only
    restore_runbook: required
```

For Docker Compose services, the preferred on-host layout is:

```text
/opt/foundation/<service>/
├─ compose.yml
├─ .env or runtime-injected environment
├─ config/
├─ data/
└─ backup/
```

For native services, Ansible should manage the config file, systemd unit, config
validation command, restart/reload behavior, and rollback of the last known-good
configuration.

## Risks and accepted trade-offs

### Accepted in phase one

- DNS has no added redundancy.
- N100 remains a known single point of failure.
- K3s control-plane HA may not span three independent physical failure domains.
- Foundation services stay outside the cluster and do not get scheduler-level
  automation.

### Must be validated before production workloads

- official TrueNAS CSI NFS RWX provisioning, snapshot, expansion, reclaim, and
  node-failure behavior;
- official TrueNAS CSI block RWO attach/detach, stale attachment recovery, and
  filesystem resize behavior;
- democratic-csi fallback viability;
- Cilium Gateway feature coverage for the required ingress use cases;
- Cilium LB/IPAM behavior on the selected VLANs;
- Harbor unavailable recovery with pre-pulled critical images;
- DNS outage recovery path;
- Foundation restore drills.

### Explicit non-goals for the first phase

- per-service automatic OPNsense firewall/DNAT rule management;
- moving Harbor, DNS, Authentik, DB, or sing-box into K3s;
- automatic upgrades of foundation services;
- using JuiceFS as the default K3s PVC or database storage layer;
- building a separate Nomad/Foundation scheduler;
- fully converting foundation hosts to NixOS;
- using NixOS, Talos Linux, Flatcar, Fedora CoreOS, or another atomic node OS
  for K3s VM nodes;
- using the ingress/service network as the K3s node identity or Cilium
  node-to-node underlay network;
- giving bare-metal K3s nodes or ordinary LAN clients storage VLAN access.

## Initial validation checklist

### Foundation

- [ ] Define foundation hosts and services as recovery units.
- [ ] Add service-level HTTP/TCP/API health checks.
- [ ] Verify backups exist for DNS, Harbor, Authentik, sing-box config, and
      external database dependencies.
- [ ] Run quarterly restore drills for critical services.
- [ ] Define break-glass local administrators or emergency tokens.
- [ ] Document the N100 single-point-of-failure risk.
- [ ] Verify Harbor-unavailable recovery using pre-pulled critical images.
- [ ] Verify DNS-unavailable recovery path.

### K3s platform interfaces

- [ ] Add common Ansible VM bootstrap for ordinary VMs and future K3s nodes.
- [ ] Add multi-NIC PVE VM support using deterministic MAC addresses and
      cloud-init network-config.
- [ ] Confirm K3s VM nodes are distributed across available PVE nodes.
- [ ] Confirm `mgmt0` is the only default-route owner.
- [ ] Confirm `cluster0` is available for K3s node identity and Cilium underlay.
- [ ] Verify Cilium installation and selected LB/IPAM mode.
- [ ] Verify Cilium node-to-node traffic uses the selected cluster underlay.
- [ ] Verify Cilium Gateway against required HTTP/TLS/Auth use cases.
- [ ] Keep Traefik as fallback until Cilium Gateway passes validation.
- [ ] Confirm Gateway/LoadBalancer VIPs are announced on the ingress/service
      network, not on the storage or cluster network.
- [ ] PoC official TrueNAS CSI for NFS RWX and block RWO.
- [ ] Validate democratic-csi fallback separately.
- [ ] Confirm storage VLAN access is limited to VM K3s nodes.
- [ ] Confirm TrueNAS CSI endpoints use storage VLAN addresses and storage
      routes, not the node default route.
- [ ] The external platform repository validates Flux bootstrap and offline
      recovery materials.
- [ ] Confirm OPNsense exposes only stable Gateway/VIP entrypoints in the first
      phase.

## Related documentation

- [Architecture notes](architecture.md)
- [Roadmap and backlog](roadmap.md)
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
