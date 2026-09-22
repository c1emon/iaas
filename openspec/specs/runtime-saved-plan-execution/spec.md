# runtime-saved-plan-execution Specification

## Purpose
Define the saved OpenTofu plan and companion-artifact contract across local and CI execution, retaining caller authorization and the explicitly bounded serial PVE workflow.

## Requirements

### Requirement: Save an applicable native plan
The runtime SHALL save a native OpenTofu plan with protected review content and the companion inputs needed to apply the exact reviewed plan from a later task.

#### Scenario: Prepare a successful plan
- **WHEN** current selected inputs pass validation and a plan is successfully prepared
- **THEN** the retained artifacts SHALL contain the native plan, necessary input/root files, provider lock and exact prepared snippets with their existing manifest
- **AND** a concise summary SHALL associate environment, root, backend/workspace, scenario, scope, input origin and image digest
- **AND** that summary SHALL retain the original required companion file list, including declared root helper files and any supplied dependency archive
- **AND** after successful native plan generation, the companion manifest SHALL record its `plan_sha256` alongside existing source/snippet digests and travel with those companion inputs
- **AND** successful plan preparation SHALL NOT upload snippets to devices or imply deployment authorization

#### Scenario: Incomplete plan preparation
- **WHEN** planning or companion-artifact preparation fails
- **THEN** the runtime SHALL report failure and SHALL NOT present partial outputs as an applicable completed plan
- **AND** sensitive partial outputs SHALL retain their protection and explicit lifecycle

### Requirement: Apply only the explicitly selected plan
The saved-plan operation SHALL consume the caller-selected native plan and its exact companion inputs without replanning, rerendering snippets or silently falling back to a direct apply.

#### Scenario: Apply across task directories
- **WHEN** the caller explicitly authorizes a retained plan under the matching runtime and target
- **THEN** it SHALL be usable from another local or CI task with its declared file relationships intact
- **AND** cloud-init validation/upload SHALL use the saved tfvars and matching manifest/snippet bytes
- **AND** arbitrary current working-tree configuration SHALL NOT replace the selected plan inputs

#### Scenario: Reject a static mismatch
- **WHEN** target, runtime version, provider lock or required companion input is missing or inconsistent
- **THEN** execution SHALL fail before snippets upload or other infrastructure writes
- **AND** it SHALL NOT substitute another plan, current input or image

#### Scenario: Reject missing original companion files
- **WHEN** a file recorded in the saved companion list is absent or the saved plan lacks that list
- **THEN** admission SHALL fail before backend initialization, snippets upload or other infrastructure writes
- **AND** admission SHALL use the saved declaration rather than current configuration or a new directory listing
- **AND** plans without the saved list SHALL require explicit replanning, without reconstructing or silently populating the list at apply time

#### Scenario: Reject mixed plan and companion artifacts
- **WHEN** a caller selects native plan A with the companion manifest and inputs from plan B, even with the same root, state, workspace and runtime
- **THEN** the runtime SHALL compare the selected native plan SHA256 with the companion manifest's `plan_sha256` before any SSH or infrastructure write
- **AND** a missing or mismatching recorded digest SHALL fail without uploading snippets or applying the plan
- **AND** apply SHALL NOT populate, replace or rebind the recorded expected digest to make the selected artifacts pass

#### Scenario: Use a matching plan binding
- **WHEN** the native plan digest matches its companion manifest and all other target, version and input checks pass
- **THEN** the saved artifacts SHALL remain usable across task directories without rerendering or changing their recorded binding

### Requirement: Preserve native state locking and stale-plan rejection
Applying a saved plan SHALL retain native S3 state locking and OpenTofu's state identity/version checks, with no automatic bypass or replan after rejection.

#### Scenario: State changed since planning
- **WHEN** OpenTofu acquires the state lock and finds that the plan does not match the current state
- **THEN** it SHALL reject the plan without executing its VM lifecycle changes
- **AND** the runtime SHALL report any already completed snippets upload as a possible side effect
- **AND** further mutation SHALL require caller review and authorization of a newly prepared plan

#### Scenario: Lock is occupied
- **WHEN** another state operation holds the native lock
- **THEN** the operation SHALL wait for a bounded interval or fail explicitly
- **AND** it SHALL NOT disable locking, force-unlock or claim that state locking covers earlier SSH writes

### Requirement: Serial complete-workflow assumption
The current workflow SHALL rely on caller-managed serialization of complete mutations, including snippets upload, and SHALL NOT claim launcher-enforced cross-entrypoint mutual exclusion.

#### Scenario: Current single-task CI and local use
- **WHEN** CI runs the complete upload/verify/apply workflow serially
- **THEN** caller guidance SHALL require local mutations to avoid overlap with CI or other local mutations in the same environment
- **AND** checks, generation and plans SHALL remain independently usable within their own operation and state-lock boundaries
- **AND** a new shared execution lock or immutable snippets scheme SHALL NOT be required for this serial workflow

#### Scenario: A phase fails
- **WHEN** upload, verification or apply fails
- **THEN** dependent phases SHALL stop and known completed effects SHALL be reported
- **AND** necessary outputs and recovery state SHALL be retained
- **AND** the runtime SHALL NOT automatically roll back, retry apply, or promise that a rejected plan caused no infrastructure writes

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
