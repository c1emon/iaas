# vm_baseline role

`vm_baseline` is a reusable Debian guest bootstrap role.

It installs inventory-declared baseline packages, manages inventory-declared
baseline services, converges or validates the hostname against the inventory
identity, reports reboot-required markers, and prints read-only network facts.

Key defaults:

- packages: none; declare `vm_baseline_packages` in inventory/group vars
- time sync packages: none; declare `vm_baseline_time_sync_packages` in
  inventory/group vars when needed
- services: none; declare `vm_baseline_services` in inventory/group vars
- hostname mode: `converge`
- reboot reporting: enabled
- network validation mode: `report`

The role is intended for ordinary VMs first and can be reused by future K3s
nodes or other Debian-based guests that share the same inventory contract.

Package and service lists are intentionally empty in role defaults so the role
stays reusable and inventory controls environment policy. Group or host
variables can manage multiple baseline packages and services without editing
role tasks. For PVE guests, see
`ansible/inventories/generated/group_vars/pve_vms.yml`.

Common Debian VM examples:

```yaml
vm_baseline_packages:
  - ca-certificates
  - curl
  - dnsutils
  - iproute2
  - jq
  - qemu-guest-agent
  - sudo

vm_baseline_time_sync_packages:
  - systemd-timesyncd

vm_baseline_services:
  - name: qemu-guest-agent
    enabled: true
    state: started
  - name: systemd-timesyncd
    enabled: true
    state: started
```
