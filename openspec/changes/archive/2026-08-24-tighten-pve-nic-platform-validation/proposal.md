## Why

Explicit VM NIC names are emitted as Linux interface names in cloud-init network-config. The current DNS-label validation accepts names that Linux cannot create, deferring a deterministic input error until guest provisioning.

## What Changes

- **BREAKING** Reject explicit NIC names longer than 15 ASCII characters before generated artifacts are accepted.
- Document that the explicit NIC name is a guest interface name, not merely a descriptive identifier.
- Add a regression test for the accepted boundary and the rejected overlength case.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pve-automation-foundation`: Explicit multi-NIC declarations must be constrained to Linux-renderable interface names.

## Impact

- `scripts/pve_inventory` validation, multi-NIC tests, and PVE inventory documentation.
- Existing valid inventory remains compatible; only unusable overlength names become invalid.
