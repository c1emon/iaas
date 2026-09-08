## MODIFIED Requirements

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the XikeOS read-only facts workflow through the relocated reusable switch playbook using collection-native facts without requiring a role that only wraps the collection call.

#### Scenario: Run read-only facts through playbook entrypoint
- **WHEN** the operator runs `automation/ansible/playbooks/switches/readonly-facts.yml` with the selected environment inventory
- **THEN** the playbook SHALL collect facts with `c1emon.xikeos.xikeos_facts`
- **AND** the workflow SHALL expose collection-native `ansible_net_*` and `ansible_network_resources` data to caller-owned export tasks
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after facts collection completes

#### Scenario: Avoid redundant read-only role wrapper
- **WHEN** read-only facts collection requires no reusable repository policy beyond runtime validation and collection module invocation
- **THEN** the workflow SHALL NOT require a dedicated `switch_readonly_facts` role
- **AND** direct playbook tasks SHALL make the native collection call and exported variables clear to operators

#### Scenario: Keep host connection settings outside playbook implementation
- **WHEN** the read-only facts workflow is used for a switch host
- **THEN** host connection settings SHALL remain supplied by selected environment inventory or runtime variables rather than being hard-coded in reusable tasks
