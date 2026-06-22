## Why

The repository is intended to become the source of truth for Astra infrastructure automation, but Proxmox VE virtual machine lifecycle management is not yet represented as code. Current automation covers OPNsense and XikeOS/SKS8300 network operations, while PVE templates, VM creation, static cloud-init addressing, Ansible inventory generation, and PCIe passthrough VM declarations remain manual.

Operators need a safe foundation for creating and managing a small PVE cluster VM fleet from declarative inventory without immediately taking over high-risk host networking, HA, or existing production VM state.

## What Changes

- Add a PVE automation foundation based on Packer, OpenTofu, the `bpg/proxmox` provider, generated inputs, and Ansible inventory output.
- Use YAML inventory as the source of truth for PVE cluster defaults, networks, templates, PCIe mappings, and VM declarations.
- Build a Debian 13 cloud-init-capable PVE template with Packer before creating VMs from it.
- Generate OpenTofu `tfvars.json` and Ansible inventory from YAML inventory rather than maintaining duplicate VM data.
- Manage new PVE VM lifecycle with OpenTofu while keeping state local at first.
- Use existing shared storage roles: `memory` for VM/template disks and `images` for ISO/import/snippets.
- Attach VMs to pre-existing bridges such as `br_dev` and `br_prod`; do not manage PVE host network interfaces in this change.
- Support declarations for existing PVE PCI resource mappings, including the current `iGpu0` mapping, through safe OpenTofu VM `hostpci` configuration.
- Reserve HA fields in inventory but keep HA automation disabled.

## Capabilities

### New Capabilities
- `pve-automation-foundation`: Define the initial source-of-truth, template build, VM provisioning, inventory generation, and passthrough guardrails for PVE automation.

### Modified Capabilities
- None.

## Impact

- New OpenSpec capability:
  - `openspec/specs/pve-automation-foundation/spec.md`
- Planned repository areas:
  - `inventory/` for YAML source-of-truth files
  - `infra/packer/proxmox/debian-13/` for Debian 13 template builds
  - `infra/tofu/pve/` for OpenTofu PVE VM lifecycle configuration
  - `ansible/inventories/generated/` for generated VM inventory
  - `docs/runbooks/` and `docs/decisions/` for operating guidance and decisions
- Operational impact:
  - First implementation targets new VMs only.
  - Existing PVE host network configuration remains a prerequisite and is not mutated.
  - Existing VMs are not imported or modified.
  - PVE HA is modeled for future use but not enabled.
  - PCIe passthrough VM support relies on existing PVE resource mappings and does not configure host IOMMU/VFIO state.
