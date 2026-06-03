# switch-readonly-facts-export-workflow Specification

## Purpose

Provide a caller-owned export workflow for writing collected switch facts and profile-approved raw outputs to repository files without making file persistence intrinsic to the switch facts role.

## Requirements

### Requirement: Playbook-level switch facts export workflow
The system SHALL provide a caller-owned export workflow for writing collected switch facts and raw outputs to repository files without making file persistence an intrinsic behavior of the facts role.

#### Scenario: Export switch facts after role collection
- **WHEN** `playbooks/switches/readonly-facts.yml` runs the read-only facts role and export is enabled by the playbook workflow
- **THEN** the playbook-level export workflow SHALL write configured structured exports from `switch_facts`
- **AND** it SHALL write files under the configured switch export directory

#### Scenario: Export raw outputs from profile export plan
- **WHEN** raw output export is enabled by the playbook workflow
- **THEN** the export workflow SHALL write raw command files from `switch_raw_export_items`
- **AND** it SHALL preserve profile-provided filenames and redacted content
- **AND** it SHALL NOT independently decide that sensitive plaintext command output is safe to write

#### Scenario: Summarize collection outside the facts role
- **WHEN** raw output export is enabled by the playbook workflow
- **THEN** the export workflow SHALL write a collection summary using role output variables such as command plan, CLI result count, profile name, gather subsets, transport, and terminal adapter

### Requirement: Export variables are caller-owned
The system SHALL keep export path, format, and raw-save controls outside the `switch_readonly_facts` role defaults.

#### Scenario: Configure export at playbook scope
- **WHEN** the operator uses the switch read-only facts playbook
- **THEN** export variables such as formats, export directory, raw output directory, and raw-save behavior SHALL be defined by the playbook or caller
- **AND** the facts role SHALL not require those variables to collect and parse facts
