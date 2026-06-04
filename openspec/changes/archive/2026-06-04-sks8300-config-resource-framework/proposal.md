## Why

Future SKS8300 configuration changes should be managed as declarative resources with planning, diff, apply, and verification rather than as arbitrary CLI command execution. Establishing the spec now keeps the read-only profile work aligned with a safe write path and borrows proven MikroTik/RouterOS Ansible patterns for resource registries and idempotent modification workflows.

## What Changes

- Add a future `switch_config` workflow for SKS8300-series configuration resources that is separate from `switch_readonly_facts`.
- Define an intent-driven configuration model using resources such as VLANs and interfaces rather than raw user-supplied config commands.
- Require a lifecycle of collect current state, parse facts, validate intent, compute diff/plan, render commands, explicitly apply, verify, and export a change report.
- Require safe defaults: check/diff mode by default, explicit apply opt-in, command guardrails, and no secret leakage in reports.
- Reuse the SKS8300 platform profile core planned by `profile-driven-sks8300-readonly-facts` for command catalog, parsing, redaction, and future resource definitions.
- Do not implement configuration mutation in the read-only facts role.

## Capabilities

### New Capabilities
- `sks8300-config-resource-framework`: Declarative SKS8300-series configuration resource planning and application framework with idempotent diff/apply/verify phases.

### Modified Capabilities
- None.

## Impact

- Future Ansible role:
  - `ansible/roles/switch_config/`
- Shared Python profile core:
  - `ansible/module_utils/switch_profiles/sks8300/`
- Future Ansible-facing filter facade additions:
  - `ansible/filter_plugins/switch_profiles.py`
- Future operator variables:
  - `switch_platform_profile`
  - `switch_config_intent`
  - `switch_config_apply`
  - `switch_config_allowed_operations`
- Documentation impact:
  - switch playbook docs must clearly distinguish read-only facts from configuration workflows
- The first implementation should start with a narrow resource scope such as VLANs and interface access/trunk membership; broader resources can follow later.
