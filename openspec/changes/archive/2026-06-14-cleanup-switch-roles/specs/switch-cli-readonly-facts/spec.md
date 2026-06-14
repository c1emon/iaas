## MODIFIED Requirements

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the XikeOS read-only facts workflow through the switch
read-only playbook using collection-native facts without requiring a separate
role when the role would only wrap `c1emon.xikeos.xikeos_facts`.

#### Scenario: Run read-only facts through playbook entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL collect facts with `c1emon.xikeos.xikeos_facts`
- **AND** the workflow SHALL expose collection-native `ansible_net_*` and `ansible_network_resources` data to caller-owned export tasks
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after facts collection completes

#### Scenario: Avoid redundant read-only role wrapper
- **WHEN** read-only facts collection requires no reusable repository policy beyond runtime validation and collection module invocation
- **THEN** the workflow SHALL NOT require a dedicated `switch_readonly_facts` role
- **AND** direct playbook tasks SHALL make the native collection call and exported variables clear to operators

#### Scenario: Keep host connection settings outside playbook implementation
- **WHEN** the read-only facts workflow is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in tasks

## REMOVED Requirements

### Requirement: Role-based read-only facts workflow packaging
**Reason**: Replaced by the modified requirement above, which allows the
read-only workflow to be playbook-owned when the role no longer adds reusable
policy beyond direct `c1emon.xikeos.xikeos_facts` invocation.

**Migration**: Use `ansible/playbooks/switches/readonly-facts.yml` as the
supported entrypoint, or call `c1emon.xikeos.xikeos_facts` directly with the same
inventory/runtime variables for custom workflows.
