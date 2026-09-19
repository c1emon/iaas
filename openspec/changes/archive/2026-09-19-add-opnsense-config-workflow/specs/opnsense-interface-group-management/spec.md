## MODIFIED Requirements

### Requirement: Explicit group execution entry
Groups SHALL use the manage-interface-groups.yml resource implementation through either direct Ansible with caller inventory and explicit target limit or the formal OPNsense configuration workflow with an exact single target and reviewed selection. For direct execution, opnsense_interface_group_source SHALL default to the environment's ansible/vars/opnsense/interface-groups.yml and accept a generated-file path. The selected source and actual loaded list SHALL both be validated before credential preflight. Runtime check/generate SHALL remain offline; device writes SHALL require explicit direct execution or configuration workflow apply.

#### Scenario: Group file is generated
- **WHEN** runtime generate emits a selected interface-groups file
- **THEN** no group write occurs until the caller explicitly invokes the corresponding Ansible playbook or applies a reviewed configuration candidate selecting those groups

#### Scenario: Direct input contains newly declared nested groups
- **WHEN** the selected group file or actual loaded list declares Inner with member lan and Outer with member Inner in either order
- **THEN** shared single-document validation rejects the nested reference before provider or credential access, even when neither group exists on the appliance

### Requirement: Group activation and access policy boundaries
The system SHALL validate the whole selected group batch and actual Ansible-loaded values before credentials, suppress per-item reload and use the fixed Collection's `oxlorg.opnsense.raw` module with the fixed POST path `firewall/group/reconfigure` once after successful changes. Check mode SHALL not mutate or reconfigure. Partial-save and activation failures SHALL be distinguished with explicit force-reload recovery. Arbitrary API paths/bodies and private API clients SHALL NOT be exposed or introduced. Reconfigure's shared filter reload effects SHALL be documented. A response that proves only request acceptance SHALL NOT be reported as confirmed activation; the configuration workflow SHALL use supported active evidence or preserve an unconfirmed outcome and stop dependent stages. Group membership SHALL NOT be interpreted as permission to access destinations or bypass interface ACL ordering.

#### Scenario: Membership affects existing policy
- **WHEN** a caller changes membership of a group referenced by rules
- **THEN** the runtime manages the specified group without synthesizing allow rules or claiming unchanged site ACL behavior

#### Scenario: Group reconfigure fails
- **WHEN** changes were saved but group reconfigure fails
- **THEN** the result reports saved/running divergence and no automatic rollback

#### Scenario: Group reconfigure uses the fixed raw path
- **WHEN** a selected group batch has changes and is not running in check mode
- **THEN** the workflow invokes the fixed Collection raw module once with `firewall/group/reconfigure`, while arbitrary endpoints and private clients remain unavailable

#### Scenario: Group response does not establish reload completion
- **WHEN** reconfigure returns ok but its API semantics do not establish successful underlying reload
- **THEN** configuration workflow activation remains unconfirmed unless supported active evidence establishes the required outcome
- **AND** dependent stages do not proceed based only on that response
