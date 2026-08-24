## ADDED Requirements

### Requirement: Protected and unprotected VM resource parity
The PVE cloud-init VM module SHALL keep its protected and unprotected VM resource definitions structurally equivalent except for the minimal differences required to select and protect the lifecycle branch.

#### Scenario: Module selects the protected resource
- **WHEN** VM lifecycle policy enables destroy protection
- **THEN** the protected resource SHALL have count `1` and the unprotected resource SHALL have count `0`
- **AND** the protected resource SHALL declare literal `lifecycle.prevent_destroy = true`

#### Scenario: Module selects the unprotected resource
- **WHEN** VM lifecycle policy disables destroy protection
- **THEN** the unprotected resource SHALL have count `1` and the protected resource SHALL have count `0`
- **AND** the unprotected resource SHALL NOT declare `lifecycle.prevent_destroy`

#### Scenario: Common VM behavior is edited
- **WHEN** a common resource argument, nested block, ignore rule, precondition, or other VM behavior changes
- **THEN** the protected and unprotected resource definitions SHALL remain identical for that behavior
- **AND** the only permitted structural differences SHALL be the resource labels, complementary count expressions, and protected-only literal `prevent_destroy = true`

### Requirement: Offline VM resource parity guard
The repository SHALL enforce protected/unprotected VM resource parity through a fail-closed offline structural check.

#### Scenario: Resource definitions remain in parity
- **WHEN** the parity guard normalizes only the explicitly permitted differences
- **THEN** the remaining protected and unprotected resource definitions SHALL compare equal
- **AND** the guard SHALL pass without provider credentials, PVE access, OpenTofu plan, state access, or mutation

#### Scenario: One resource drifts
- **WHEN** either resource differs in an argument, nested block, lifecycle ignore rule, precondition, or other content outside the explicit allowlist
- **THEN** the parity guard SHALL fail
- **AND** it SHALL report an actionable normalized diff identifying the one-sided change

#### Scenario: Guard structure is missing or ambiguous
- **WHEN** either expected resource/guard marker is missing, duplicated, misordered, or cannot be normalized using the exact permitted-difference rules
- **THEN** the parity guard SHALL fail rather than skip or broaden its comparison

#### Scenario: Root aggregate offline validation runs
- **WHEN** an operator or CI runs the root aggregate offline check
- **THEN** it SHALL execute the VM resource parity guard through the existing repository test path
- **AND** the guard SHALL NOT rewrite HCL or change OpenTofu state

### Requirement: Intentional duplication is documented and preserved
The module SHALL document why the two VM resources remain separate and how their parity is maintained.

#### Scenario: Maintainer reviews the duplicated resources
- **WHEN** a maintainer opens the PVE cloud-init VM module
- **THEN** source comments SHALL explain that lifecycle destroy protection requires a static resource-level declaration
- **AND** the comments SHALL identify the exact allowed differences and the offline parity guard

#### Scenario: Maintainer considers merging the resources
- **WHEN** a future refactor proposes removing the duplicated resources or changing their addresses
- **THEN** that work SHALL require a separate reviewed change with explicit state-migration and lifecycle-safety analysis
- **AND** this parity change SHALL NOT perform that refactor
