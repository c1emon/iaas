## REMOVED Requirements

### Requirement: Debian 13 PVE template build foundation
**Reason**: The combined node-build foundation and its force/foundation-spike scenarios are superseded by independent image construction and HTTPS publication. Keeping the old scenarios would assert a retired workflow.
**Migration**: Switch directly to the new image and pve-template contracts after draining old tasks and retaining original evidence. No legacy alias or record translator is provided.

### Requirement: Separate PVE API and SSH automation identities
**Reason**: The old requirement mandates a Packer PVE token, retired template-build wrapper and broad preflight sudo override. Image construction now has no PVE identity and publication uses HTTPS.
**Migration**: Provision caller-owned publisher API permissions and only still-required dedicated node SSH access; drain old work and retain recovery evidence before removing obsolete template credentials, helpers and sudo entries. No old write path remains available.

## ADDED Requirements

### Requirement: Independent Debian image and PVE publication foundation
The system SHALL provide a reusable Debian 13 image tool and independent PVE template publication, with typed build configuration separate from target VM/template configuration.

#### Scenario: Reuse one constructed image
- **WHEN** a caller builds a selected Debian 13 amd64 cloud image
- **THEN** the tool SHALL deliver a self-contained cleaned qcow2 and evidence using pinned base checksum and runtime/profile identities
- **AND** separate publication SHALL configure a new PVE template using explicit target/storage/hardware inputs without installing packages or rebuilding the disk
- **AND** the same artifact MAY be published again to another compatible admitted target without another build

#### Scenario: Separate site and instance settings
- **WHEN** infra-ops supplies image settings
- **THEN** source mirrors, packages, locale and timezone SHALL be typed build inputs
- **AND** PVE node/VMID/storage/bridge and per-instance Cloud-init identity SHALL NOT be baked into the reusable image

#### Scenario: Replace the old foundation
- **WHEN** the new capability is enabled
- **THEN** the placeholder Packer, node image-building path and old combined build inputs SHALL be retired without legacy aliases or adapters
- **AND** occupied templates SHALL never be force-replaced; old tasks and raw records SHALL be drained/retained and ownership reconciled before removing helper assets

### Requirement: Dedicated publication and restricted node identities
The system SHALL separate image-building, template-publication, OpenTofu and node SSH credentials according to the selected operation, with identity provisioning and secret resolution owned by the caller.

#### Scenario: Configure PVE API automation
- **WHEN** a caller configures publisher and OpenTofu API credentials
- **THEN** each operation SHALL use a dedicated scoped token with the complete permissions required by its lifecycle, rather than root or personal credentials
- **AND** publisher scope SHALL cover observation, allocation, conversion and owned-resource cleanup, including import upload and deletion permissions on its dedicated staging store
- **AND** image construction SHALL receive no PVE API token and SHALL NOT require a Packer PVE identity

#### Scenario: Bootstrap API trust outside the consuming root
- **WHEN** initial API users, tokens and ACLs are prepared
- **THEN** the caller SHALL establish them before the consuming runtime starts and SHALL supply secrets through operation-scoped injection or protected files
- **AND** privilege-separated PVE token permissions SHALL be granted at both user and token scopes as required, including SDN.Use for selected SDN bridge access
- **AND** the OpenTofu root using those credentials SHALL NOT manage its own initial user, token or ACL root of trust

#### Scenario: Retain only necessary node helpers
- **WHEN** the independent VM snippet-upload capability requires node SSH
- **THEN** the caller SHALL supply a dedicated non-root automation identity, its key and strict known_hosts verification
- **AND** root-owned helpers SHALL use mode 0750, validated fixed arguments and wrapper-only sudo rules with no broad preflight override
- **AND** template building, disk import, VM configuration, conversion and deletion SHALL NOT use node CLI fallback
- **AND** publication SHALL NOT require node SSH or deploy a space-probe helper merely because receiving-node temporary capacity is not observable through HTTPS
- **AND** bootstrap SHALL validate helper and sudo configuration without invoking facility mutations, and SHALL NOT modify global SSHD policy

#### Scenario: Document and perform helper cutover
- **WHEN** bootstrap documentation or helper assets are updated
- **THEN** documentation SHALL describe publisher/OpenTofu ACLs, caller-controlled secret injection and only the helpers still required by declared capabilities
- **AND** independent iaas-pve-snippet-upload access SHALL be preserved where used; this change SHALL NOT add an upload-space helper
- **AND** obsolete template worker/build helper assets, tokens and sudo rules SHALL be removed only after active tasks are drained and ownership/pending recovery is reconciled with original evidence retained
- **AND** new callers SHALL NOT fall back to old names, old write protocols or a separate old lock domain

## MODIFIED Requirements

### Requirement: Local state and safety documentation
The system SHALL keep state and recovery artifacts excluded from Git and document the selected S3 launcher contract alongside explicitly retained local-state entrypoints.

#### Scenario: Use local state safely for initial operation
- **WHEN** operators use an existing explicit local-state PVE root
- **THEN** OpenTofu state SHALL remain owned by that selected root/backend and excluded from Git
- **AND** documentation SHALL describe its single-operator assumptions, backups and recovery
- **AND** adoption of the new caller-configured S3 launcher SHALL NOT silently migrate or replace that state

#### Scenario: Back up local state during helper operations
- **WHEN** a helper runs an apply-like OpenTofu operation with local state
- **THEN** it SHALL back up local state under the selected ignored runtime backup directory
- **AND** legacy state and backups from before the repository cutover SHALL not be migrated or restored
- **AND** this file-copy helper SHALL NOT be represented as backing up S3; S3 write failures SHALL retain their separate recovery state

#### Scenario: Preserve tool ownership boundaries
- **WHEN** PVE automation is documented
- **THEN** OpenTofu SHALL own business VM lifecycle and hardware attachment, while the iaas image tool uses Packer QEMU and supported configuration/cleaning tools to produce independent disk images
- **AND** the iaas HTTPS publisher SHALL own image-to-template publication and its resource lifecycle without system customization, while Ansible SHALL own selected guest configuration/verification
- **AND** infra-ops SHALL own execution infrastructure, orchestration, artifact upload/retention, site parameters and promotion
- **AND** PVE host networking, OPNsense, and switch mutation SHALL remain outside normal VM lifecycle operations

#### Scenario: Keep DNS management out of scope
- **WHEN** VMs are provisioned with static cloud-init IPs
- **THEN** the foundation SHALL NOT create or update DNS, DHCP, or host override records
- **AND** documentation SHALL state that name resolution requires manual work or a later automation change
