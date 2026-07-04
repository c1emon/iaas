## Why

K3s VM nodes need distinct management, cluster-underlay, storage, and ingress
interfaces, but the current PVE VM model supports only one NIC and one
cloud-init IP configuration per VM. Multi-NIC cloud-init support is needed before
the K3s bootstrap design can provision predictable node networking.

## What Changes

- Extend VM inventory to support an ordered list of declared NICs with roles,
  logical networks, static IPs, deterministic MAC addresses, optional gateway,
  and optional DNS settings.
- Preserve backward compatibility for existing single-NIC VM declarations where
  practical, or provide a generated migration path without changing existing VM
  behavior.
- Generate OpenTofu VM inputs that can attach multiple NICs to resolved PVE
  bridges and pass deterministic MAC addresses to the provider.
- Generate cloud-init `network-config` snippets that match NICs by MAC address,
  assign stable interface names, configure addresses, and enforce a single
  default route.
- Update validation to reject duplicate MACs, duplicate IPs, invalid CIDRs,
  non-attachable networks, multiple default gateways, missing management NICs,
  and inconsistent DNS/gateway declarations.
- Keep PVE host bridge/VLAN creation out of scope; this change only attaches VM
  NICs to existing approved bridges.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `pve-automation-foundation`: VM source-of-truth, generation, validation,
  OpenTofu lifecycle, and cloud-init behavior are extended from single-NIC to
  multi-NIC guest networking.

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
