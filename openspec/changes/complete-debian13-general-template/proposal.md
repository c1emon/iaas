## Why

infra-ops needs a Debian 13 general template for its current PVE deployment contract. Publication currently requires a NIC, Packer silently uses its default virtual capacity, and customization does not offer an explicit package upgrade. Offline check must reject unsupported inputs with useful, credential-free locations.

## What Changes

- Add explicit build output `disk_size_gib` (including 8 GiB) and boolean `customization.package_upgrade`; reject unsupported shrinking before provisioning, verify final capacity and retain it in the artifact.
- Allow publication `hardware.bridge: null` to mean no NIC. Omit net0 at creation, verify absence of every NIC and retain the actual configuration in record/v3.
- Clean build network state, credentials and instance identity while retaining cloud-init network initialization, growpart/resizefs and enabled QEMU Guest Agent.
- Complete the existing offline check paths for build, publication and clone declarations: strict fields, relationships, capability checks and safe file/field/reason diagnostics.
- Reuse full clone, pool, independent network/identity injection and disk growth. Extend only a proven gap in the bounded acceptance path for DNS and 128 GiB growth.
- Release fixed runtime/image-builder versions and run one representative real build → publish → full clone → first boot → guest checks → exact cleanup path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `image-build-tool`: explicit capacity, upgrades and clone-ready cleanup.
- `pve-template-lifecycle`: explicit publication without a NIC.
- `runtime-environment-config`: actionable offline checking of current inputs.
- `pve-template-acceptance`: representative clone network and disk-growth verification.

## Impact

Current contracts/schema, QEMU/Ansible profile, validators/runtime, examples and focused regressions. No legacy adapters, pool implementation, infra-ops edits, daily apply enablement, permission/credential management or business acceptance. Template 9000 is retained for handoff; only this execution's temporary VM, volumes, snippets, build credentials and working resources are cleaned. Occupied VMID/IP or unconfirmed ownership blocks dependent writes.
