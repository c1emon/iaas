## Why

The switch read-only facts playbook now contains connection validation, command collection, parsing, export generation, and raw-output handling in one long playbook. Splitting the implementation into a role will make the workflow easier to review, reuse, validate, and extend while preserving the existing read-only SSH behavior.

## What Changes

- Refactor `ansible/playbooks/switches/readonly-facts.yml` into a thin entrypoint that invokes a dedicated Ansible role.
- Add a `switch_readonly_facts` role with focused task files for validation, directory preparation, CLI collection, parsing, and export writing.
- Move switch facts workflow defaults that are implementation defaults into the role, while keeping host connection credentials and `network_cli` adapter settings in inventory/group variables.
- Preserve the current approved command list, mutation guardrails, parser behavior, generated facts schema, export paths, and raw running-config redaction behavior.
- Update switch playbook documentation to describe the role layout and validation commands.
- No behavior change is intended; this is an implementation modularization.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `switch-cli-readonly-facts`: Add a packaging requirement that the read-only facts workflow is exposed through a reusable role while preserving current collection and export behavior.

## Impact

- Affected Ansible entrypoint:
  - `ansible/playbooks/switches/readonly-facts.yml`
- New role structure under:
  - `ansible/roles/switch_readonly_facts/`
- Affected switch documentation:
  - `ansible/playbooks/switches/README.md`
  - possibly `ansible/README.md`
- Existing parser/filter plugin remains in `ansible/filter_plugins/switch_cli_facts.py` unless implementation reveals a low-risk reason to move it.
- No changes to switch CLI command semantics, SSH credential variables, generated export schema, or live validation expectations.
