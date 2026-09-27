## ADDED Requirements

### Requirement: Consistent PVE API private CA and insecure semantics
PVE preflight, health, VM reads and result verification SHALL use a consistent TLS selection. With `pve.insecure: false`, an optional caller private CA SHALL augment system public trust while certificate chain, validity period and endpoint IP or DNS identity verification remain enabled. With `pve.insecure: true`, certificate verification SHALL remain disabled regardless of whether a CA file is supplied.

#### Scenario: Strict API access uses the caller CA
- **WHEN** strict mode supplies a valid PEM CA file or CA bundle and the endpoint presents a currently valid matching certificate chained to a trusted CA
- **THEN** each PVE API adapter SHALL establish verified TLS using that trust selection
- **AND** system public roots SHALL remain available

#### Scenario: Strict API access rejects invalid trust or identity
- **WHEN** strict mode cannot load the supplied CA, cannot build a trusted certificate chain, or encounters a certificate outside its validity period or with a mismatching endpoint IP or DNS identity
- **THEN** the operation SHALL fail with a safe error identifying the CA or TLS verification failure
- **AND** it SHALL NOT silently retry with certificate verification disabled or discard the supplied CA to continue
- **AND** an empty or unloadable caller CA SHALL fail even if system public roots could otherwise verify the endpoint
- **AND** callers SHALL receive a safe CA failure reason or a failed TLS phase with a protected diagnostic location through the existing runtime and launcher reporting contract

#### Scenario: Explicit insecure overrides a supplied CA
- **WHEN** `pve.insecure: true` and a CA file is supplied, including one with empty or invalid PEM contents
- **THEN** the API adapter SHALL skip certificate verification without loading or validating the unused CA contents
- **AND** the existing selected-file transport and access rules SHALL still apply

#### Scenario: No private CA is supplied
- **WHEN** strict mode runs without a private CA
- **THEN** PVE API access SHALL retain system default certificate verification without requiring a new CA input
