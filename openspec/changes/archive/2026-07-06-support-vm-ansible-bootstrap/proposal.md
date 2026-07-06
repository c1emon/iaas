## Why

Repository-managed PVE guests currently stop at cloud-init reachability and a
read-only verification workflow. K3s automation and ordinary long-lived VMs need
a shared, idempotent Ansible bootstrap layer so cloud-init remains only the
first-boot handoff and guests can be converged to a predictable baseline before
K3s-specific roles are added.

## What Changes

- Add an explicit Ansible workflow for bootstrapping repository-declared PVE
  guest VMs from the generated inventory.
- Introduce a common VM baseline role for ordinary Debian cloud-image guests,
  covering host identity, base packages, qemu-guest-agent, time sync, apt
  configuration, SSH/sudo expectations, and safe reboot reporting.
- Keep guest network mutation out of scope for the first version; bootstrap may
  validate declared guest network facts but must not rewrite guest NIC, route, or
  DNS configuration.
- Reuse the generated `pve_vms` inventory and `ops` SSH user rather than adding
  a parallel host source of truth.
- Document how this common bootstrap becomes the base layer for future K3s node
  bootstrap roles.

## Capabilities

### New Capabilities

- `vm-ansible-bootstrap`: Defines the explicit, repository-owned Ansible
  workflow for converging declared PVE guest VMs to a common baseline.

### Modified Capabilities

- None.

## Impact

- Affected code: `ansible/playbooks/pve/`, new Ansible roles under
  `ansible/roles/`, generated PVE inventory usage, documentation, and Makefile or
  command entrypoints if present.
- Affected systems: Debian-based PVE guest VMs declared in repository inventory.
- Safety boundary: does not create, destroy, start, stop, or reconfigure VMs;
  does not mutate PVE host networking, OPNsense, switches, K3s, or guest network
  configuration.
- Dependencies: existing cloud-init VM creation and generated Ansible inventory;
  operator SSH authentication through the existing `ops` user.
