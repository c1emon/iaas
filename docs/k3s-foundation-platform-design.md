# K3s application platform and foundation services design

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

### Repository boundaries

K3s-related automation should be split by responsibility rather than placed in a
single catch-all GitOps tree.

This repository remains the IaaS and platform repository. It is responsible for
the parts required to create, connect, operate, and recover the application
platform:

```text
iaas repository
├─ Proxmox / OpenTofu infrastructure
├─ Ansible host and foundation automation
├─ OPNsense and switch automation
├─ foundation service recovery model
├─ K3s node bootstrap
├─ Cilium baseline configuration
├─ Gateway baseline configuration
├─ TrueNAS CSI / StorageClass baseline
├─ Flux bootstrap
├─ platform validation checks
└─ disaster recovery runbooks
```

Application workloads should live in a separate GitOps application repository
once the platform is past initial PoC:

```text
apps GitOps repository
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
├─ source: iaas repository
│  └─ cluster bootstrap and core platform primitives
└─ source: apps GitOps repository
   └─ application workloads and day-to-day app releases
```

Temporary application PoCs may live in this repository while the platform is
being validated, but they should be isolated under an explicit PoC path and
migrated out before becoming routine application operations. The long-term rule
is:

```text
cluster creation, platform wiring, and recovery belong here;
ordinary application deployment and upgrades belong in the apps GitOps repo.
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

### Gateway implementation

Cilium Gateway is the first implementation candidate. Traefik remains the
fallback and comparison point.

Only one Gateway implementation should own a production hostname/VIP set at a
time.

### GitOps

Flux is the GitOps controller choice.

Flux must not depend on Authentik login to recover the cluster. kubeconfig,
Flux bootstrap material, age keys, and required manifests need an offline
recovery path.

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
- fully converting foundation hosts to NixOS.

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

- [ ] Verify Cilium installation and selected LB/IPAM mode.
- [ ] Verify Cilium Gateway against required HTTP/TLS/Auth use cases.
- [ ] Keep Traefik as fallback until Cilium Gateway passes validation.
- [ ] PoC official TrueNAS CSI for NFS RWX and block RWO.
- [ ] Validate democratic-csi fallback separately.
- [ ] Confirm storage VLAN access is limited to VM K3s nodes.
- [ ] Validate Flux bootstrap and offline recovery materials.
- [ ] Confirm OPNsense exposes only stable Gateway/VIP entrypoints in the first
      phase.

## Related documentation

- [Architecture notes](architecture.md)
- [Roadmap and backlog](roadmap.md)
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
