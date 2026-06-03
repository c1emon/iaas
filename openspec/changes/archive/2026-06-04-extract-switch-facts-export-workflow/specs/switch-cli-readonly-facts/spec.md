## MODIFIED Requirements

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the SKS8300 read-only facts workflow through a reusable Ansible role that collects and parses facts without intrinsic file persistence side effects, while preserving the existing playbook entrypoint behavior through caller-owned export tasks.

#### Scenario: Run read-only facts through role entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL invoke a dedicated switch read-only facts role
- **AND** the role SHALL collect the approved SSH `network_cli` command outputs
- **AND** the role SHALL parse structured switch facts into role output variables
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after the role completes

#### Scenario: Keep host connection settings outside role defaults
- **WHEN** the role is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in role tasks

### Requirement: YAML and JSON exports
The system SHALL support configurable YAML and JSON export of parsed switch facts through the playbook-level export workflow rather than through the facts role itself.

#### Scenario: Export selected formats
- **WHEN** the playbook-level export workflow is enabled and the user configures YAML, JSON, or both output formats
- **THEN** the export workflow SHALL write the selected structured export files from `switch_facts`
- **AND** the `switch_readonly_facts` role SHALL remain usable without writing those files

### Requirement: Export location
The system SHALL allow the playbook-level export workflow to write generated switch exports under the repository `exports/` directory in a switch-specific subdirectory.

#### Scenario: Write exports under repository exports tree
- **WHEN** switch facts are exported for inventory host `sw-core`
- **THEN** generated outputs SHALL be written under `exports/switches/sw-core/` or a timestamped child directory beneath it by the export workflow
- **AND** the facts role SHALL not create export directories as part of facts collection

### Requirement: Secret redaction for raw running configuration
The system SHALL ensure any saved raw running configuration output is redacted before being written by the playbook-level export workflow.

#### Scenario: Redact plaintext user password
- **WHEN** raw `show running-config` output contains a line such as `username admin privilege 15 password 0 admin`
- **THEN** any saved raw running configuration export SHALL replace the secret value with a redacted placeholder
- **AND** the redacted content SHALL come from the profile-generated raw export plan consumed by the export workflow

#### Scenario: Redact network management secrets
- **WHEN** raw configuration output contains password, RADIUS secret, TACACS secret, or SNMP community lines
- **THEN** any saved raw running configuration export SHALL redact the secret values before writing the file
- **AND** the facts role SHALL not write raw configuration files directly
