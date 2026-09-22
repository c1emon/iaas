## ADDED Requirements

### Requirement: PVE plan review and native execution unit
PVE plan/apply SHALL operate on the explicit complete root with a private native plan and a safe machine-readable review, not a second executable VM candidate format.

#### Scenario: Review destructive and uncertain changes
- **WHEN** a native plan includes create, update, delete, replacement, no-op or unknown values
- **THEN** the review SHALL preserve those distinctions and replacement ordering
- **AND** deletion from removed declarations and potentially disruptive changes SHALL be visible for caller approval
- **AND** uncertain disruption SHALL remain unknown rather than a safe update

#### Scenario: Attempt partial or direct apply
- **WHEN** a caller requests a targeted subset, direct apply without a saved plan, or implicit replanning
- **THEN** the formal PVE execution path SHALL reject the request without VM or snippet writes

### Requirement: Bind the actual PVE API target
Saved PVE plans SHALL bind the actual supported provider target, TLS selection, root, backend/workspace, runtime and companion inputs, independently of authentication secrets.

#### Scenario: API target differs from the reviewed target
- **WHEN** the effective API endpoint or supported provider configuration conflicts with the saved target even though root ID and SSH host match
- **THEN** admission SHALL fail before infrastructure writes
- **AND** credentials SHALL NOT silently select another API target

#### Scenario: Unsupported provider topology
- **WHEN** a root uses unrecognized dynamic target configuration, multiple PVE targets or provider aliases outside the supported contract
- **THEN** the runtime SHALL reject it explicitly rather than claim analysis of arbitrary HCL

### Requirement: Verification requirements travel with the reviewed plan
The saved companions and review SHALL fix verification categories, scope, required or optional status and execution responsibility alongside the native plan.

#### Scenario: Review configuration and guest acceptance
- **WHEN** a caller prepares a plan with configuration checks and any caller-owned guest acceptance requirements
- **THEN** configuration verification SHALL remain mandatory and guest checks SHALL be identified as required or optional with their caller-owned scope or fixed policy reference
- **AND** apply, independent verify and results SHALL preserve that association rather than downgrade requirements or substitute current policy after review
- **AND** missing caller-owned evidence SHALL remain unconfirmed without requiring a new guest execution engine in IaaS

### Requirement: Bind clone dependencies to current template admission
Plans requiring template cloning SHALL retain the template construction or historical observation association with the native plan and SHALL recheck current admission and actual object identity before mutation.

#### Scenario: Apply a clone plan later
- **WHEN** a caller applies a retained clone plan
- **THEN** the runtime SHALL require a current caller admission bound to that plan, execution, target, template record and use purpose
- **AND** it SHALL perform the pve-template-lifecycle current-object checks before snippet upload
- **AND** missing, revoked, replaced or unknown references SHALL require reconciliation or a new plan rather than substitution

### Requirement: Authentication can change without changing the plan
The runtime SHALL keep planned configuration and rendered guest material fixed while accepting operation-specific authentication through the supported execution-time credential contract.

#### Scenario: Rotate provider credentials between plan and apply
- **WHEN** the caller supplies fresh valid credentials for the same reviewed target
- **THEN** apply SHALL use the fresh credentials and original plan without rerendering cloud-init or changing planned configuration
- **AND** secret values SHALL NOT be used as plan identity or public binding fields

#### Scenario: Root freezes authentication in ordinary input variables
- **WHEN** a root does not meet the supported execution-time provider authentication contract
- **THEN** the runtime SHALL reject the root with migration guidance instead of assuming environment variables override saved values

### Requirement: No-change does not hide prerequisite effects
PVE no-change reporting SHALL distinguish native resource differences from actual workflow side effects.

#### Scenario: Empty resource diff still uploads snippets
- **WHEN** the selected plan has no native resource changes but execution uploads snippets
- **THEN** the result SHALL report the upload and SHALL NOT label the whole execution side-effect-free no_change
- **AND** native stale-plan rejection after upload SHALL preserve the upload fact or uncertainty and recovery material

### Requirement: New PVE plans require the new contract
The runtime SHALL reject saved plans lacking the new target, authentication, state-admission and applicable template-association contract rather than modify old materials to make them pass.

#### Scenario: Consume a legacy saved plan
- **WHEN** a caller supplies a v1 PVE saved-plan bundle to the new lifecycle
- **THEN** admission SHALL fail before infrastructure writes with instructions to prepare a new plan
- **AND** old plan and recovery materials SHALL remain available for investigation without replay or implicit upgrade
