# PVE PCIe passthrough readiness

Use this as a host-side checklist before enabling a passthrough VM.

## Manual checks

- Confirm the VM declaration uses a resource mapping such as `iGpu0`.
- Confirm the target node is allowed by the mapping (`cohe` or `node3` for `iGpu0`).
- Confirm the VM uses `q35`, `ovmf`, and `cpu_type = host`.
- Confirm HA is disabled for the VM.
- Confirm the host already has IOMMU/VFIO configured by the platform team.
- Confirm the device is present and bound as expected on the host.

## Important limitations

- Do **not** automate IOMMU, VFIO, or kernel parameter changes from this repository.
- Do **not** rely on automatic node migration for passthrough VMs.
- Do **not** treat passthrough as a blocker for first disposable VM acceptance; it is Phase B work.

## Apply-time expectation

- OpenTofu will render `hostpci` blocks from mapping names.
- OpenTofu will not mutate host PCI state.
- If a VM needs passthrough, the host must already be ready before apply.

## Future automation direction

- Keep VM lifecycle and hardware-mapping bootstrap separate.
- `bpg/proxmox` `~> 0.109` provides `proxmox_hardware_mapping_pci`, which can manage PVE PCI resource mappings such as `iGpu0`.
- If this repository later automates mapping creation, prefer a dedicated bootstrap root such as `infra/tofu/pve-mappings/` instead of the normal VM lifecycle root.
- Run that bootstrap root with explicit high-privilege credentials only when changing mappings; current research indicates hardware mapping management may require `root@pam` or equivalent elevated mapping permissions.
- The normal `infra/tofu/pve` VM root should continue to consume mapping names through `hostpci { mapping = "..." }` and should not create, update, or delete cluster hardware mappings during routine VM applies.
- `make pve-preflight` now performs the repository-owned read-only PCI mapping check before VM apply; it does not create or modify mappings.

Example future OpenTofu shape:

```hcl
resource "proxmox_hardware_mapping_pci" "igpu0" {
  name = "iGpu0"

  map = [
    {
      node        = "cohe"
      path        = "0000:00:02.1"
      id          = "8086:xxxx"
      iommu_group = 15
    },
    {
      node        = "node3"
      path        = "0000:00:02.1"
      id          = "8086:xxxx"
      iommu_group = 13
    },
  ]
}
```
