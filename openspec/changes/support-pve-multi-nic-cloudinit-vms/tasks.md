## 1. Inventory schema and normalization

- [ ] 1.1 Extend VM inventory validation to accept an explicit `nics` list with name, role, network, MAC address, static IP, gateway, and DNS fields.
- [ ] 1.2 Preserve legacy single-NIC VM declarations by normalizing `network`, `static_ip`, `gateway`, and `dns` into one management NIC.
- [ ] 1.3 Add validation for duplicate NIC names, duplicate MAC addresses, duplicate IP addresses, invalid MAC format, invalid CIDR, and unknown networks.
- [ ] 1.4 Add validation that explicit NIC declarations have exactly one management NIC and at most one default gateway.
- [ ] 1.5 Add validation that each NIC network is attachable for VMs and each NIC IP belongs to that network CIDR.
- [ ] 1.6 Add tests proving unchanged legacy single-NIC inventory produces unchanged generated artifacts.

## 2. Generated artifacts

- [ ] 2.1 Extend `generated.auto.tfvars.json` to include normalized NIC metadata for each VM.
- [ ] 2.2 Extend generated Ansible inventory so multi-NIC VMs use the management NIC host address as `ansible_host`.
- [ ] 2.3 Include declared NIC metadata in generated Ansible host variables for later bootstrap and verification workflows.
- [ ] 2.4 Update generated VM documentation to show each VM NIC, role, network, bridge, MAC, IP, gateway, and DNS summary.
- [ ] 2.5 Add generated-output stale checks for the new multi-NIC and cloud-init metadata.

## 3. Cloud-init network-config rendering

- [ ] 3.1 Extend the cloud-init renderer to emit network-config snippets for VMs with explicit NIC declarations.
- [ ] 3.2 Render cloud-init network-config v2 using `match.macaddress`, `set-name`, static addresses, one default route, and deterministic DNS settings.
- [ ] 3.3 Extend the local cloud-init manifest to record snippet kind, file ID, byte count, and SHA-256 checksum for both user-data and network-config snippets.
- [ ] 3.4 Extend cloud-init upload to upload all manifest-recorded snippet artifacts without implicit re-rendering.
- [ ] 3.5 Extend cloud-init verification to checksum-verify all manifest-recorded snippet artifacts without printing secrets.
- [ ] 3.6 Add tests for single-NIC user-data-only rendering and multi-NIC user-data plus network-config rendering.

## 4. OpenTofu module updates

- [ ] 4.1 Update the PVE cloud-init VM module to render dynamic `network_device` blocks from normalized NIC metadata.
- [ ] 4.2 Set declared MAC addresses on OpenTofu network devices using the provider-supported attribute name.
- [ ] 4.3 Preserve the current single-NIC provider `ip_config` path for legacy VMs where appropriate.
- [ ] 4.4 Add provider custom cloud-init network-config references for multi-NIC VMs using the rendered snippet file IDs.
- [ ] 4.5 Update module variables, locals, outputs, and lifecycle ignore rules as needed for network-config snippets.
- [ ] 4.6 Run `tofu fmt` and `tofu validate` for the PVE OpenTofu configuration.

## 5. Documentation and examples

- [ ] 5.1 Update PVE inventory documentation with legacy single-NIC and explicit multi-NIC VM examples.
- [ ] 5.2 Document deterministic MAC planning and the recommendation to use MAC matching plus stable interface names.
- [ ] 5.3 Document the K3s target NIC roles: `mgmt0`, `cluster0`, `storage0`, and `ingress0`.
- [ ] 5.4 Document safety boundaries: no PVE bridge/VLAN creation, no OPNsense or switch mutation, and no post-boot guest network mutation.
- [ ] 5.5 Document render, upload, verify, plan, and apply workflow changes for cloud-init network-config snippets.

## 6. Validation

- [ ] 6.1 Run `uv run --directory . pytest`.
- [ ] 6.2 Run `uv run --directory . yamllint inventory ansible/inventories/generated/pve.yml`.
- [ ] 6.3 Run `make pve-check` and confirm generated artifacts are fresh.
- [ ] 6.4 Run `make pve-validate` or equivalent OpenTofu validation without contacting live infrastructure beyond existing validation boundaries.
- [ ] 6.5 Run relevant cloud-init render and verify-unit tests for manifest behavior.
- [ ] 6.6 Run `openspec status --change support-pve-multi-nic-cloudinit-vms` and confirm the change is apply-ready.
