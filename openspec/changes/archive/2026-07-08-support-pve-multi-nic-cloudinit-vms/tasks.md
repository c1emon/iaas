## 1. Inventory schema and normalization

- [x] 1.1 Extend VM inventory validation to accept an explicit `nics` list with name, role, network, MAC address, static IP, gateway, and DNS fields.
- [x] 1.2 Migrate existing inventory to explicit `nics` declarations and remove the legacy top-level single-NIC fields.
- [x] 1.3 Add validation for duplicate NIC names, duplicate MAC addresses, duplicate IP addresses, invalid MAC format, invalid CIDR, and unknown networks.
- [x] 1.4 Add validation that explicit NIC declarations support zero or more NICs, at most one default route, and at most one Ansible connection NIC.
- [x] 1.5 Add validation that each NIC network is attachable for VMs and each NIC IP belongs to that network CIDR.
- [x] 1.6 Add tests proving the explicit inventory model, zero-NIC support, and legacy-field rejection.

## 2. Generated artifacts

- [x] 2.1 Extend `generated.auto.tfvars.json` to include normalized NIC metadata for each VM.
- [x] 2.2 Extend generated Ansible inventory so multi-NIC VMs use the NIC marked for Ansible connectivity as `ansible_host`.
- [x] 2.3 Include declared NIC metadata in generated Ansible host variables for later bootstrap and verification workflows, without reintroducing removed aliases.
- [x] 2.4 Update generated VM documentation to show each VM NIC, role, network, bridge, MAC, IP, route, and DNS summary.
- [x] 2.5 Add generated-output stale checks for the new multi-NIC and cloud-init metadata.

## 3. Cloud-init network-config rendering

- [x] 3.1 Extend the cloud-init renderer to emit network-config snippets for VMs with explicit NIC declarations.
- [x] 3.2 Render cloud-init network-config v2 using `match.macaddress`, `set-name`, static addresses, explicit default-route metadata, and deterministic DNS settings.
- [x] 3.3 Extend the local cloud-init manifest to record snippet kind, file ID, byte count, and SHA-256 checksum for both user-data and network-config snippets.
- [x] 3.4 Extend cloud-init upload to upload all manifest-recorded snippet artifacts without implicit re-rendering.
- [x] 3.5 Extend cloud-init verification to checksum-verify all manifest-recorded snippet artifacts without printing secrets.
- [x] 3.6 Add tests for explicit user-data plus network-config rendering and zero-NIC user-data-only rendering.

## 4. OpenTofu module updates

- [x] 4.1 Update the PVE cloud-init VM module to render dynamic `network_device` blocks from normalized NIC metadata.
- [x] 4.2 Set declared MAC addresses on OpenTofu network devices using the provider-supported attribute name.
- [x] 4.3 Remove the provider legacy `ip_config` path and drive networking from explicit NIC metadata only.
- [x] 4.4 Add provider custom cloud-init network-config references for multi-NIC VMs using the rendered snippet file IDs.
- [x] 4.5 Update module variables, locals, outputs, and lifecycle ignore rules as needed for network-config snippets.
- [x] 4.6 Run `tofu fmt` and `tofu validate` for the PVE OpenTofu configuration.

## 5. Documentation and examples

- [x] 5.1 Update PVE inventory documentation with the explicit generic NIC model and zero-NIC examples.
- [x] 5.2 Document deterministic MAC planning and the recommendation to use MAC matching plus stable interface names.
- [x] 5.3 Document the K3s target NIC roles as a future specialization of the generic base model: `mgmt0`, `cluster0`, `storage0`, and `ingress0`.
- [x] 5.4 Document safety boundaries: no PVE bridge/VLAN creation, no OPNsense or switch mutation, and no post-boot guest network mutation.
- [x] 5.5 Document render, upload, verify, plan, and apply workflow changes for cloud-init network-config snippets.

## 6. Validation

- [x] 6.1 Run `uv run --directory . pytest`.
- [x] 6.2 Run `uv run --directory . yamllint inventory ansible/inventories/generated/pve.yml`.
- [x] 6.3 Run `make pve-check` and confirm generated artifacts are fresh.
- [x] 6.4 Run `make pve-validate` or equivalent OpenTofu validation without contacting live infrastructure beyond existing validation boundaries.
- [x] 6.5 Run relevant cloud-init render and verify-unit tests for manifest behavior.
- [x] 6.6 Run `openspec status --change support-pve-multi-nic-cloudinit-vms` and confirm the change is apply-ready.
