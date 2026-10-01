## MODIFIED Requirements

### Requirement: VM clone inputs consume the new template record directly
The PVE VM planning and execution paths SHALL consume pve-template-record/v3 and current caller template admission directly, without an old-record adapter or changes to native OpenTofu state ownership.

#### Scenario: Plan a clone from a new publication or observation
- **WHEN** the native VM plan depends on a selected template
- **THEN** companions SHALL bind its new record identity, exact target/UUID/volume/configuration expectations and verification requirements
- **AND** apply SHALL revalidate current native identity and caller admission before facility mutation
- **AND** observation-only records SHALL NOT claim build history and required missing evidence SHALL block dependent acceptance

#### Scenario: Receive a legacy reference
- **WHEN** a caller supplies an old template record or a plan dependent on that old contract
- **THEN** the operation SHALL reject and require a fresh new-schema observation/publication record and new plan
- **AND** it SHALL NOT mutate/import/rewrite state, infer identity from VMID alone or alter OPNsense's native candidate model

## ADDED Requirements

### Requirement: Saved VM plans freeze pool and VMID policy
Ordinary VM planning SHALL preserve effective per-VM pool placement, caller acceptance reservation policy and concrete VMIDs in existing native-plan/companion review bindings. Saved execution SHALL consume only those approved inputs and independently recheck effective pool permissions and relevant current occupancy before facility writes. Creation SHALL precheck all necessary allocation, audit and configuration/lifecycle permissions before facility writes. If future pool-derived authority cannot be established, admission SHALL refuse rather than discover missing authority after clone. Existing VM update/delete permission checks SHALL remain in place.

#### Scenario: Approved pool or reserved interval changes
- **WHEN** selected inputs or companions differ from the reviewed pool, VMID or acceptance reservation policy
- **THEN** saved execution SHALL reject rather than regenerate, move to another pool, drop placement or select another VMID
- **AND** changing policy or placement SHALL require a newly reviewed plan and approval

#### Scenario: Current managed VM is updated
- **WHEN** the selected native state and caller ownership identify an existing VM and its pool change is explicitly included in a new native plan
- **THEN** the normal reviewed native update MAY proceed after current permission/ownership checks
- **AND** create-time free-VMID checks SHALL NOT reject a legitimate state-owned update merely because that VM exists

### Requirement: Concrete VMID conflicts use caller serialization
The caller SHALL atomically reserve and serialize concrete VMIDs per selected cluster across ordinary VM, template publication, acceptance and recovery conflicts. IaaS SHALL require current vmid_reservation admission matching the approved stable cluster scope, exact protected VMID set, consumption reservation and serialization context, and recheck native occupancy, without claiming a new global locking service or that an admission file alone proves cross-Runner exclusion.

#### Scenario: Two requests reserve the same cluster VMID
- **WHEN** another caller workflow already reserves the same concrete VMID
- **THEN** the caller SHALL refuse the competing reservation and IaaS SHALL reject a conflicting or missing admission without dependent writes
- **AND** neither path SHALL change numbers, overwrite an existing VM or expand the admitted interval

#### Scenario: A VMID becomes occupied after planning
- **WHEN** a new create/clone reaches admission with its selected VMID occupied or visibility insufficient
- **THEN** IaaS SHALL reject that write and retain the exact conflict/unknown evidence
- **AND** native state locking SHALL NOT be described as protecting acceptance/publication outside that state

#### Scenario: Same cluster is accessed through another node endpoint
- **WHEN** two caller workflows use different node API endpoints of the same cluster
- **THEN** their protected cluster/VMID scope SHALL remain the same and conflicting reservations SHALL be refused
- **AND** IaaS SHALL reject an admission whose cluster scope or VMID set differs from its approved request/plan
