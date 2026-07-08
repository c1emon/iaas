## Why

K3s VM nodes need distinct management, cluster-underlay, storage, and ingress
interfaces. The PVE VM inventory has now been migrated to the explicit generic
NIC model, with K3s-specific role constraints to be specialized later.

## What Changes

- Extend VM inventory to support an ordered list of declared NICs with semantic
  roles, logical networks, static IPs, deterministic MAC addresses, explicit
  default-route metadata, explicit Ansible-connection metadata, optional
  gateways, and optional DNS settings.
- Use the explicit `nics` model everywhere and avoid any legacy single-NIC VM
  shape in source inventory or generated artifacts.
- Generate OpenTofu VM inputs that can attach multiple NICs to resolved PVE
  bridges and pass deterministic MAC addresses to the provider.
- Generate cloud-init `network-config` snippets that match NICs by MAC address,
  assign stable interface names, configure addresses, and honor explicit
  default-route metadata.
- Update validation to reject duplicate MACs, duplicate IPs, invalid CIDRs,
  non-attachable networks, duplicate default routes, duplicate Ansible
  connection NICs, and legacy top-level NIC fields.
- Keep PVE host bridge/VLAN creation out of scope; this change only attaches VM
  NICs to existing approved bridges.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pve-automation-foundation`: VM source-of-truth, generation, validation,
  OpenTofu lifecycle, and cloud-init behavior use the explicit generic NIC
  model for multi-NIC guest networking.

## Impact

- Affected code: `inventory/pve-cluster.yml`, `inventory/vms.yml`,
  `scripts/pve_inventory/`, `infra/tofu/modules/pve-cloudinit-vm/`,
  `infra/tofu/pve/`, cloud-init snippet rendering/upload/verification,
  generated OpenTofu tfvars, generated Ansible inventory, tests, and docs.
- Affected systems: new or updated PVE VMs created from repository inventory.
- Safety boundary: does not create PVE bridges, VLANs, OPNsense interfaces,
  switch ports, firewall rules, K3s clusters, or guest OS network state after
  first boot.
- Dependencies: existing Debian cloud-init template, existing PVE bridges marked
  attachable for VM NICs, and deterministic MAC planning in inventory.
