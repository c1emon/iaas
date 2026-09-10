## ADDED Requirements

### Requirement: Repair-first implementation gate
This change SHALL complete and validate existing-runtime repairs before dependency upgrades or new OPNsense capability implementation.

#### Scenario: A prerequisite repair remains incomplete
- **WHEN** any repair task 0.1–0.14 or the repair gate 0.15 is incomplete
- **THEN** tasks 1–5 SHALL remain blocked from implementation
- **AND** design or audit test results SHALL NOT be treated as completed repair evidence

#### Scenario: Repair phase is accepted
- **WHEN** targeted regressions, affected Ansible checks, the existing offline gate and final-image smoke pass
- **THEN** actual software evidence SHALL be recorded separately before beginning the reviewed dependency refresh
- **AND** no live infrastructure qualification, release publication or destructive recovery SHALL be implied

### Requirement: Working-directory independent lifecycle entrypoints
The OCI and checkout entrypoints SHALL resolve their own Makefile and nested targets without requiring the caller to run from the implementation directory.

#### Scenario: A lifecycle command runs from an external working directory
- **WHEN** the caller invokes PVE plan, apply or destroy through the shipped entrypoint
- **THEN** recursive commands SHALL use the explicitly selected implementation Makefile
- **AND** the caller's directory SHALL remain available for its own files without becoming the implicit implementation root

### Requirement: CI validates the shipped execution baseline
The main checkout gate SHALL use the shipped OpenTofu version and explicitly installed Collection baseline, with realistic representative operation-state regressions.

#### Scenario: Main CI installs infrastructure tools
- **WHEN** the gate prepares its toolchain
- **THEN** it SHALL use coordinated fixed versions rather than latest OpenTofu or unpinned shared Collections
- **AND** the existing source-versus-dependency image layering SHALL remain intact

#### Scenario: Repaired orchestration is validated
- **WHEN** regression tests exercise lifecycle entrypoints
- **THEN** safe substitutes SHALL run through actual orchestration for installed, partial, failed-activation and arbitrary-directory states
- **AND** constant all-success synthetic facts alone SHALL NOT satisfy that coverage

### Requirement: Coordinated execution dependency updates
Runtime dependency updates SHALL keep the developer environment and OCI image compatible and reproducible without expanding a focused capability change into an unrelated toolchain refresh.

#### Scenario: The Ansible distribution requires a newer core patch
- **WHEN** this change upgrades the reviewed Ansible distribution to 14.4.0
- **THEN** the runtime core pin and uv lock SHALL be updated together to the reviewed 2.21.4 baseline
- **AND** explicitly installed shared Collections SHALL be aligned between developer and image manifests using the reviewed candidate versions
- **AND** oxlorg.opnsense SHALL remain pinned to 26.1.11 unless a separately evidenced compatibility requirement changes that decision

#### Scenario: Dependency inputs change
- **WHEN** the Python or Collection dependency pins are updated
- **THEN** the final runtime image SHALL be rebuilt with the updated dependency layer and pass relevant existing runtime smoke checks and synthetic validation
- **AND** dependency resolution alone SHALL NOT be reported as image or appliance compatibility
- **AND** subsequent repository-source edits SHALL preserve separation from dependency installation layers

#### Scenario: The focused refresh is accepted
- **WHEN** the reviewed dependency upgrade passes software validation
- **THEN** its versions and evidence SHALL be recorded separately from new OPNsense functionality
- **AND** unrelated providers, base images and tools SHALL NOT be upgraded implicitly
- **AND** neither real-appliance changes nor image publication SHALL be implied
