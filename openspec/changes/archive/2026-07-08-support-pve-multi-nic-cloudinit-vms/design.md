## Context

The current PVE VM automation model has been migrated to the explicit generic
NIC model. A VM declares a `nics` list with semantic roles, explicit route and
Ansible-connectivity metadata, and deterministic MAC addresses. Runtime
cloud-init support renders user-data plus network-config snippets when NICs are
present.

The K3s platform design will eventually require VM nodes with separate
management, cluster-underlay, storage, and ingress/service interfaces. The base
PVE model should stay generic now, with those K3s-specific roles and constraints
specialized later. Multi-NIC guests still need stable MAC addresses, predictable
guest interface names, explicit route metadata, explicit Ansible-connection
metadata, and clear validation before OpenTofu applies changes.

## Goals / Non-Goals

**Goals:**

- Represent multiple NICs per VM in repository YAML inventory.
- Use the explicit `nics` model in source inventory and generated artifacts.
- Validate NIC roles, networks, IPs, MAC addresses, gateways, DNS settings, and
  generated metadata offline before OpenTofu runs.
- Generate OpenTofu input for multiple PVE VM `network_device` attachments.
- Generate cloud-init `network-config` snippets using MAC matching and stable
  guest interface names.
- Upload and verify network-config snippets with the same exact-artifact model
  used for runtime user-data snippets.
- Render Ansible inventory so `ansible_host` comes from the NIC explicitly
  marked for Ansible connectivity.

**Non-Goals:**

- Creating or modifying PVE bridges, VLANs, SDN zones, switch ports, OPNsense
  interfaces, firewall rules, or DNS records.
- Managing guest networking after first boot with Ansible.
- Installing K3s, Cilium, Flux, or storage plugins.
- Supporting DHCP-based multi-NIC guests in the first version.
- Managing IPv6 multi-NIC behavior unless already supported by existing single-IP
  validation.
- Automatically generating MAC addresses without operator review.

## Decisions

### Use `nics` as the source-of-truth VM network shape

VM declarations should use a `nics` list. Legacy top-level single-NIC fields are
not accepted. The generic base model does not require a management NIC.

Example target shape:

```yaml
nics:
  - name: mgmt0
    role: management
    network: prod
    macaddr: bc:24:11:00:00:21
    static_ip: 10.50.0.21/24
    gateway: 10.50.0.254
    dns: [10.50.0.254]
  - name: cluster0
    role: cluster
    network: k3s-cluster
    macaddr: bc:24:11:00:01:21
    static_ip: 10.20.0.21/24
    gateway: null
```

Alternative considered: replace the single-NIC schema immediately. This was
rejected because existing VM examples and tests should remain valid while the
new multi-NIC model is introduced.

### Treat Ansible connectivity as explicit metadata

For multi-NIC VMs, generated Ansible inventory should set `ansible_host` to the
host address of the NIC explicitly marked `ansible_connection: true`. Default
routes should be driven by explicit `default_route: true` metadata, not by the
NIC role.

Alternative considered: require a management NIC again. This was rejected
because the generic base model should not encode K3s-specific role semantics.

### Require deterministic operator-declared MAC addresses for multi-NIC VMs

Multi-NIC cloud-init network-config should match interfaces by MAC address and
assign stable names with `set-name`. MAC addresses should be stored in reviewed
inventory and validated for uniqueness.

Alternative considered: rely on Proxmox-generated MAC addresses or guest
interface ordering such as `ens18`, `ens19`, and `ens20`. This was rejected
because cloud-init network-config must exist before first boot, and interface
order is too fragile for multi-NIC K3s nodes.

### Render both user-data and network-config runtime snippets

The existing runtime cloud-init renderer should be extended to render a
network-config artifact for each VM that uses `nics`. OpenTofu should reference
both snippets through the provider's custom cloud-init mechanism where supported.
The base model no longer uses provider `ip_config` for VM networking.

Alternative considered: encode multi-NIC network YAML inside user-data. This was
rejected because cloud-init has a dedicated network-config channel and Proxmox
supports custom network snippets.

### Use dynamic OpenTofu `network_device` blocks

The PVE cloud-init VM module should render one network device per NIC. Each
network device should resolve its bridge from the logical network and set the
declared MAC address. Explicit zero-NIC declarations should remain valid and
render no devices.

Alternative considered: create separate modules for single-NIC and multi-NIC
VMs. This was rejected because it would duplicate VM lifecycle behavior and make
future K3s VM declarations harder to maintain.

### Keep host bridge ownership external

Network declarations remain logical references to existing PVE bridges. Offline
validation should reject NICs attached to networks that are not marked attachable
for VMs. Online preflight may verify bridge existence, but this change does not
create bridges or VLANs.

Alternative considered: add PVE bridge/VLAN creation in the same change. This
was rejected because host network mutation is higher risk and belongs in a
separate, explicit capability.

## Risks / Trade-offs

- **Wrong MAC assignment can swap guest interfaces** → Require explicit MACs,
  validate uniqueness, render MAC-based cloud-init matching, and include
  generated artifacts for review.
- **Multiple default routes can break routing** → Offline validation rejects
  more than one `default_route: true` NIC per VM.
- **Provider cloud-init custom network support may differ by version** → Confirm
  the exact `bpg/proxmox` attribute names during implementation and spike one
  multi-NIC VM plan before broad refactoring.
- **Explicit NIC migration may show output churn** → Regenerate committed outputs
  from the explicit `nics` source of truth and review the diffs carefully.
- **Non-attachable storage networks could be accidentally exposed** → Require
  network declarations to opt into VM attachment and keep current non-attachable
  networks rejected.
- **Runtime snippets contain operational topology** → Keep rendered snippets in
  ignored cache directories and committed generated files non-sensitive.

## Migration Plan

1. Use the explicit NIC data model as the only VM network declaration shape.
2. Extend generated OpenTofu tfvars and Ansible inventory with normalized NIC
   metadata.
3. Extend cloud-init rendering to emit network-config artifacts and a manifest.
4. Extend upload/verify wrappers or calls to handle both user-data and
   network-config snippets.
5. Update the OpenTofu VM module to render dynamic network devices and reference
   network-config snippets for VMs with NICs.
6. Add tests for explicit inventory, zero-NIC support, and legacy-field rejection.
7. Update documentation with the explicit model and the K3s NIC specialization.

Rollback is source-based: correct the explicit NIC YAML and re-render. If a VM
was created with wrong NICs, destroy/recreate only that VM when it is safe, or
repair it manually in PVE and reconcile inventory afterward.

## Open Questions

- Should the first multi-NIC K3s example be committed in `inventory/vms.yml`, or
  should examples remain documentation-only until the K3s bootstrap change?
- Should MAC addresses be fully operator-authored, or should a later helper
  generate deterministic suggestions that still require review?
- Should gateway-less NICs allow explicit non-default routes in this version, or
  should they be deferred until Cilium/ingress routing needs are known?
