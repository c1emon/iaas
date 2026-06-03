## ADDED Requirements

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the SKS8300 read-only facts workflow through a reusable Ansible role while preserving the existing playbook entrypoint behavior.

#### Scenario: Run read-only facts through role entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL invoke a dedicated switch read-only facts role
- **AND** the workflow SHALL still collect the approved SSH `network_cli` command outputs, parse structured switch facts, write configured exports, and redact raw running configuration secrets as specified by the existing requirements

#### Scenario: Keep host connection settings outside role defaults
- **WHEN** the role is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in role tasks
