## Why

The SKS8300 read-only facts role currently collects, parses, and writes files, which makes persistence an implicit built-in side effect instead of a caller-selected behavior. Separating export from facts collection keeps the role focused as a facts provider and gives playbooks control over whether, where, and how outputs are saved.

## What Changes

- **BREAKING**: Remove the built-in export phase from `switch_readonly_facts`; the role will produce in-memory facts and export-plan variables only.
- Add a playbook-level export workflow for `playbooks/switches/readonly-facts.yml` so the current switch playbook can still write `facts.yml`, `facts.json`, raw-output files, and README when explicitly enabled by the playbook.
- Move export path/format/raw-save variables out of the role defaults and into the playbook/export workflow scope.
- Preserve parsed fact schema, profile-driven command planning, raw export policy generation, and redaction behavior.
- Update documentation to present file export as an optional consumer workflow rather than an inherent role capability.

## Capabilities

### New Capabilities

- `switch-readonly-facts-export-workflow`: Optional playbook-level persistence workflow for writing collected switch facts and raw outputs to repository export files.

### Modified Capabilities

- `switch-cli-readonly-facts`: Change the role packaging requirement so the role returns facts/outputs without writing files, while the playbook may invoke a separate export workflow.
- `sks8300-profile-readonly-facts`: Clarify that profile raw export policy produces an export plan for consumers; file writing is handled outside the profile-driven facts role.

## Impact

- Affected Ansible role:
  - `ansible/roles/switch_readonly_facts/`
- Affected playbook entrypoint and playbook-local tasks:
  - `ansible/playbooks/switches/readonly-facts.yml`
  - new or moved export task file under `ansible/playbooks/switches/`
- Affected defaults/variables:
  - remove export defaults from the facts role
  - define export variables at playbook or export-task scope
- Affected documentation:
  - `ansible/playbooks/switches/README.md`
  - `ansible/roles/switch_readonly_facts/README.md`
- No switch configuration mutation is introduced by this change.
