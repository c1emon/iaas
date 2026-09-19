# opnsense-interface-group-management Specification

## Purpose
Manage explicitly declared firewall interface groups and membership with native identity and reference protection, while leaving access policy, grouping decisions and deployment sequencing under caller control.

## Requirements

### Requirement: Independent firewall interface group resource
The system SHALL accept opnsense_interface_groups in interface-groups.yml under interface-groups selection. Identity SHALL be the native name. Present SHALL require a valid name, nonempty unique member list, strict boolean gui_group and valid group sequence; description SHALL be optional. Absent SHALL require only name/state. The initial contract SHALL reject nested groups, NAT-style scope/slug and enabled fields. Member identifiers SHALL follow verified provider/API semantics, never guessed translations from GUI labels.

#### Scenario: Update existing membership
- **WHEN** a valid group retains its name but changes members
- **THEN** only the declared group is updated without duplicating it or automatically changing rule source-address conditions

#### Scenario: System groups are undeclared
- **WHEN** the appliance contains undeclared built-in or VPN groups including empty groups
- **THEN** they remain untouched and are not forced into the caller's present-record contract

#### Scenario: Optional description is removed
- **WHEN** a present group omits its previously configured description
- **THEN** the description is cleared and a repeated declaration is unchanged

### Requirement: Existing group-capable references remain compatible
Group identity SHALL preserve native case. Existing filter-rule interfaces and matching context.interface_networks keys SHALL accept valid group names wherever native group references are supported, including legal unresolved external references. This compatibility SHALL NOT widen physical-interface fields in VIPs/Gateways or infer address authorization from membership. Existing deny and inversion protections SHALL remain effective using explicit validated network context.

#### Scenario: Mixed-case group is referenced
- **WHEN** a selected present group named Internal is referenced by a valid filter rule and explicit network-context key of the same name
- **THEN** offline and actual-loaded-input validation accept and preserve the case, subject to the existing rule safety checks

#### Scenario: Group syntax is used in a physical-interface field
- **WHEN** a VIP or Gateway specifies an interface invalid under its existing physical-interface contract
- **THEN** the group-reference extension does not make that field valid

### Requirement: Explicit group execution entry
Groups SHALL use the manage-interface-groups.yml resource implementation through either direct Ansible with caller inventory and explicit target limit or the formal OPNsense configuration workflow with an exact single target and reviewed selection. For direct execution, opnsense_interface_group_source SHALL default to the environment's ansible/vars/opnsense/interface-groups.yml and accept a generated-file path. The selected source and actual loaded list SHALL both be validated before credential preflight. Runtime check/generate SHALL remain offline; device writes SHALL require explicit direct execution or configuration workflow apply.

#### Scenario: Group file is generated
- **WHEN** runtime generate emits a selected interface-groups file
- **THEN** no group write occurs until the caller explicitly invokes the corresponding Ansible playbook or applies a reviewed configuration candidate selecting those groups

#### Scenario: Direct input contains newly declared nested groups
- **WHEN** the selected group file or actual loaded list declares Inner with member lan and Outer with member Inner in either order
- **THEN** shared single-document validation rejects the nested reference before provider or credential access, even when neither group exists on the appliance

### Requirement: Reference-safe group lifecycle
The system SHALL reject deletion when selected surviving rules reference the group and SHALL respect appliance-side reference protection for references outside selected inputs. It SHALL NOT cascade-delete rules, implicitly rename groups or rewrite appliance-wide references. Legal external group references SHALL remain distinct from locally verified membership facts and SHALL NOT require a complete appliance graph.

#### Scenario: Selected rule still uses deleted group
- **WHEN** a selected group is absent while a selected surviving rule refers to it
- **THEN** local admission fails before any mutation

#### Scenario: An external rule prevents deletion
- **WHEN** appliance-side checks find an unselected surviving reference
- **THEN** deletion fails clearly without removing that rule or bypassing the native guard

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
