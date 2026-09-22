## ADDED Requirements

### Requirement: VM clone inputs consume the new template record directly
The PVE VM planning and execution paths SHALL consume pve-template-record/v2 and current caller template admission directly, without an old-record adapter or changes to native OpenTofu state ownership.

#### Scenario: Plan a clone from a new publication or observation
- **WHEN** the native VM plan depends on a selected template
- **THEN** companions SHALL bind its new record identity, exact target/UUID/volume/configuration expectations and verification requirements
- **AND** apply SHALL revalidate current native identity and caller admission before facility mutation
- **AND** observation-only records SHALL NOT claim build history and required missing evidence SHALL block dependent acceptance

#### Scenario: Receive a legacy reference
- **WHEN** a caller supplies an old template record or a plan dependent on that old contract
- **THEN** the operation SHALL reject and require a fresh new-schema observation/publication record and new plan
- **AND** it SHALL NOT mutate/import/rewrite state, infer identity from VMID alone or alter OPNsense's native candidate model
