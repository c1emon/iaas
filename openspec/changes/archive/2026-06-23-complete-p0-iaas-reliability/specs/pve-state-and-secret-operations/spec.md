## ADDED Requirements

### Requirement: PVE state and cache runbooks
The system SHALL document local state and cache handling for PVE automation workflows.

#### Scenario: Operator reviews local OpenTofu state handling
- **WHEN** an operator needs to understand PVE OpenTofu state ownership
- **THEN** documentation SHALL identify the local state path and backup location
- **AND** it SHALL describe when to run the state backup helper
- **AND** it SHALL describe a restore path for recovering from an unintended local state change

#### Scenario: Operator reviews cache sensitivity
- **WHEN** an operator needs to inspect or clean ignored cache directories
- **THEN** documentation SHALL identify known repository cache paths used by PVE automation
- **AND** it SHALL distinguish non-sensitive generated review artifacts from ignored runtime-derived cache files
- **AND** it SHALL describe which cache contents may include secrets, password hashes, rendered cloud-init data, state backups, or other sensitive material

### Requirement: Runtime secret injection conventions
The system SHALL document how runtime secrets enter automation commands without being committed to the repository.

#### Scenario: Operator runs a command requiring PVE, OPNsense, switch, Packer, OpenTofu, or VM user secrets
- **WHEN** a workflow requires runtime credentials or VM user material
- **THEN** documentation SHALL direct the operator to inject those values through explicit runtime environment mechanisms such as `op run --env-file ...`
- **AND** it SHALL identify which environment templates or conventions apply to the workflow
- **AND** it SHALL state that plaintext secrets, private keys, token secrets, password hashes, and environment-specific secret values MUST NOT be committed

#### Scenario: Operator reviews generated files before commit
- **WHEN** an operator reviews generated outputs for commit
- **THEN** documentation SHALL identify which generated outputs are intended to be committed
- **AND** it SHALL state that committed generated outputs must remain non-sensitive
- **AND** it SHALL provide guidance for treating generated outputs as unsafe if unexpected credential-like values appear

### Requirement: Pre-operation and recovery checklist
The system SHALL provide an operator checklist for safe local PVE automation around plan/apply-like workflows.

#### Scenario: Operator prepares for an explicit online or mutation-capable workflow
- **WHEN** an operator prepares to run PVE plan, apply, destroy, template build, or guest verification commands
- **THEN** documentation SHALL describe the relevant pre-checks for state backup, secret injection, cache handling, and generated output freshness
- **AND** it SHALL keep those commands explicit and outside the default offline validation path

#### Scenario: Operator needs recovery guidance after a failed local workflow
- **WHEN** a local PVE automation workflow fails after changing local state or cache files
- **THEN** documentation SHALL point to state backup restoration and cache cleanup guidance
- **AND** it SHALL avoid recommending automatic infrastructure mutation as a recovery step
