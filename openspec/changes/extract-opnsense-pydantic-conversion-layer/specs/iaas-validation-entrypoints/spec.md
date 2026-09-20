## ADDED Requirements

### Requirement: Executable conversion invariants and dependency boundaries
The offline gate SHALL check bounded normalization properties and the established dependency direction of common primitives, OPNsense conversion and pure declaration validation. These checks SHALL require no infrastructure access or runtime credentials and SHALL not replace existing deterministic regression cases.

#### Scenario: Conversion property fails
- **WHEN** normalization changes an already canonical record, mutates its input, mishandles equivalent aliases or exposes synthetic sensitive input
- **THEN** the relevant property check fails with a reproducible counterexample
- **AND** generated cases remain bounded to the declared input domain

#### Scenario: Pure layer imports execution behavior
- **WHEN** common imports a domain or online adapter, conversion imports a workflow executor or transport, or pure declaration validation imports an online workflow adapter
- **THEN** the repository-owned dependency check fails in both local and CI validation
- **AND** normal domain-to-common imports remain permitted
