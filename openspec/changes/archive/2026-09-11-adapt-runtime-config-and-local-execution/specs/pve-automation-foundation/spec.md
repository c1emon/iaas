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
- **THEN** OpenTofu SHALL own VM lifecycle and hardware attachment, Ansible SHALL own guest configuration/verification, and Packer SHALL own reusable template construction
- **AND** PVE host networking, OPNsense, and switch mutation SHALL remain outside normal VM lifecycle operations

#### Scenario: Keep DNS management out of scope
- **WHEN** VMs are provisioned with static cloud-init IPs
- **THEN** the foundation SHALL NOT create or update DNS, DHCP, or host override records
- **AND** documentation SHALL state that name resolution requires manual work or a later automation change

### Requirement: Ordered current-input PVE lifecycle execution
PVE planning and direct apply SHALL use current generated inputs. Explicit saved-plan application SHALL instead use the validated inputs retained with that plan. Both paths SHALL preserve required execution order independently of caller working directory and Make parallelism.

#### Scenario: Caller enables parallel Make
- **WHEN** direct apply executes with parallel MAKEFLAGS
- **THEN** rendering SHALL finish before upload, upload before remote verification, and verification before OpenTofu apply
- **AND** failure of any phase SHALL stop dependent phases

#### Scenario: Generated inputs are stale
- **WHEN** planning or direct apply inputs no longer match the selected authored inventory
- **THEN** the workflow SHALL fail before remote writes or lifecycle execution
- **AND** it SHALL NOT silently regenerate caller-authored configuration

#### Scenario: Caller applies a saved plan
- **WHEN** an explicitly authorized saved plan is applied
- **THEN** static target/version and retained-input checks SHALL finish before upload, upload before remote verification, and verification before native saved-plan application
- **AND** the workflow SHALL NOT rerender snippets, replan, mix current working-tree inputs into the plan or fall back to direct apply
- **AND** native stale-state rejection SHALL report any earlier upload and SHALL NOT imply zero infrastructure side effects

### Requirement: Cloud-init consumption is bound to the current source
Upload and verification SHALL compare their explicitly selected tfvars input with the source hash recorded in the rendered manifest before any SSH call. For a saved-plan operation, the authoritative tfvars SHALL be the input retained with that plan; other operations SHALL use their explicit current source.

#### Scenario: Source is missing or different
- **WHEN** the operation's authoritative tfvars are missing, unreadable or differ from the manifest source hash
- **THEN** upload and verification SHALL fail before SSH even if all snippet checksums match the old manifest

#### Scenario: Exact rendered artifacts are consumed
- **WHEN** source and snippet checksums match
- **THEN** upload and verification SHALL use those artifacts without rerendering
- **AND** existing restrictive handling of cloud-init secrets SHALL remain in force
- **AND** saved-plan execution SHALL preserve prepared password hashes without requiring fixed salts or fresh password rendering
