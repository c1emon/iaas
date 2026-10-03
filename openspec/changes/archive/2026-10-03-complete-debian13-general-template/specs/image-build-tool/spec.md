## ADDED Requirements

### Requirement: Explicit Debian virtual disk capacity
The current build request SHALL declare whole-GiB output disk_size_gib separately from executor budgets. The Debian 13 profile SHALL support 8 GiB and SHALL reject smaller capacities and unsupported shrink operations before provisioning. Final actual capacity SHALL equal the request and be retained in artifact.disk.virtual_size_bytes before build success.

#### Scenario: Construct an 8 GiB image
- **WHEN** a supported checksummed base fits the requested 8 GiB capacity
- **THEN** Packer SHALL receive an explicit 8 GiB virtual disk size and successful output SHALL record exactly 8589934592 virtual bytes

#### Scenario: Capacity cannot be met
- **WHEN** requested capacity is below the profile minimum, smaller than the inspected base, or differs from the final inspected output
- **THEN** build SHALL fail with the capacity reason and SHALL NOT deliver a successful artifact or silently truncate partitions/filesystems

### Requirement: Explicit build-time package upgrade
The builder SHALL accept only a boolean customization.package_upgrade. Enabling it SHALL refresh selected Debian 13 repositories and upgrade installed packages to versions available at build time. Failed index refresh, upgrade or package installation SHALL prevent successful artifact delivery.

#### Scenario: Upgrade using selected mirrors
- **WHEN** package_upgrade is true and Tsinghua Debian and Debian security mirrors are selected
- **THEN** construction SHALL use trixie, trixie-updates and trixie-security and complete the package upgrade during construction
- **AND** clones SHALL NOT need another package upgrade to satisfy this build contract

#### Scenario: Upgrade fails
- **WHEN** the package manager cannot complete the selected upgrade
- **THEN** the build SHALL fail and SHALL NOT present a pre-upgrade disk as a successful requested artifact

### Requirement: Clone-ready network and growth cleanup
The delivered general image SHALL retain cloud-init, root partition/filesystem growth and enabled QEMU Guest Agent. Cleanup SHALL remove build credentials, instance identity, generated build network configuration and cloud-init instance state without permanently disabling cloud-init network configuration.

#### Scenario: First boot with independent clone configuration
- **WHEN** the clone receives a fresh identity and network before its first boot
- **THEN** cloud-init SHALL initialize that identity/network and automatically expand the root partition and filesystem to the larger disk
