## ADDED Requirements

### Requirement: Caller-owned private CA input for PVE VM operations
The launcher SHALL accept optional `files.api_ca` for PVE VM online operations through its existing selected-file transport contract. The CA SHALL remain caller-owned and SHALL NOT require embedding site certificates in the generic runtime image.

#### Scenario: Supply a private CA to an online VM operation
- **WHEN** a caller selects PVE preflight, health, read or plan with `files.api_ca`
- **THEN** local Docker and DinD SHALL make the selected file available at its mapped task path
- **AND** the operation SHALL preserve the existing public trust-file protection rules without treating the CA as an authentication secret

#### Scenario: Offline operations do not consume API trust files
- **WHEN** a caller selects offline check, generate or independent dependency preparation
- **THEN** the operation SHALL NOT load or require `files.api_ca`

#### Scenario: Transfer a saved plan with private CA material
- **WHEN** a caller selects apply or verify with a saved plan that includes private CA material
- **THEN** the launcher SHALL transfer and retain that material with the selected companions in both local Docker and DinD modes
- **AND** it SHALL NOT require the original caller CA path or substitute the current environment's `files.api_ca`
