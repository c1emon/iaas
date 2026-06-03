## Context

The current SKS8300 read-only facts workflow is implemented as a single playbook at `ansible/playbooks/switches/readonly-facts.yml`. It validates SSH/network CLI settings, creates export directories, runs the approved read-only commands, normalizes command output, builds structured facts through `switch_cli_facts`, writes YAML/JSON exports, writes optional raw output, and generates a README.

That implementation works, but the playbook now mixes orchestration with reusable implementation details. The repository already uses small task includes for some OPNsense preflight logic, but there are currently no Ansible roles. A role is the right boundary for this switch workflow because the switch facts logic is a coherent reusable unit with defaults, task sequencing, and documentation.

## Goals / Non-Goals

**Goals:**

- Convert `readonly-facts.yml` into a thin role-based entrypoint.
- Add a `switch_readonly_facts` role with focused task files for validation, preparation, collection, parsing, and exports.
- Move workflow implementation defaults into role defaults where safe.
- Keep host connection settings and runtime SSH credentials in inventory/group variables.
- Preserve current behavior, including command allowlist, mutation guardrails, parser output schema, export paths, raw-output filenames, and redaction.
- Keep validation commands straightforward for syntax checks, linting, and live `sw-core` verification.

**Non-Goals:**

- Do not add switch configuration or VLAN write management.
- Do not change the approved command list.
- Do not change the generated `facts.yml` / `facts.json` schema.
- Do not move or rewrite the Python parser/filter plugin unless required for role integration.
- Do not convert this into a custom Python Ansible module.
- Do not introduce support for additional switch platforms.

## Decisions

### Use an Ansible role, not a custom module

The workflow is mostly orchestration around existing Ansible modules plus local filters. A role keeps those concerns visible and testable in YAML while avoiding the complexity of writing and maintaining a custom Ansible module.

Alternative considered: custom Python module. Rejected because command execution, connection handling, and file exports already map well to existing Ansible primitives.

### Keep the playbook as a thin entrypoint

`readonly-facts.yml` should keep play-level concerns such as target hosts, `gather_facts`, and `connection`, then invoke `switch_readonly_facts`. This makes the entrypoint easy to understand while preserving existing operator commands.

Alternative considered: move the playbook entirely into the role and require a different entrypoint. Rejected because it would unnecessarily change the operator interface.

### Split role tasks by workflow phase

The role should use this task layout:

- `tasks/main.yml`: ordered imports only
- `tasks/validate.yml`: credentials, adapter, format, and command safety assertions
- `tasks/prepare.yml`: export directory creation
- `tasks/collect.yml`: `cli_command` loop and raw stdout selection
- `tasks/parse.yml`: normalization, named command outputs, structured facts, redaction
- `tasks/export.yml`: YAML/JSON/raw exports and generated README

This maps directly to the current playbook flow and makes each file small enough to review independently.

Alternative considered: fewer files such as `collect.yml` and `export.yml` only. Rejected because validation and parsing are distinct safety-critical phases.

### Move workflow defaults to role defaults, keep connection variables in inventory

Role defaults should own values that are intrinsic to the workflow and safe to override, such as `switch_cli_pagination_command`, `switch_cli_show_commands`, `switch_export_formats`, and export paths. Inventory/group variables should continue to own `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, `ansible_port`, and `ansible_command_timeout` because they describe host connection behavior and runtime credentials.

Alternative considered: move all switch variables into role defaults. Rejected because credentials and connection settings are inventory concerns and should remain obvious to operators.

### Keep `switch_cli_facts.py` in the existing top-level filter plugin path

The current filter plugin is already available to the playbook. Keeping it in `ansible/filter_plugins/` minimizes discovery risk and avoids coupling the parser to one role path before there is a need.

Alternative considered: move the filter plugin into `roles/switch_readonly_facts/filter_plugins/`. Rejected for this change to keep the refactor behavior-preserving and low risk.

## Risks / Trade-offs

- Role defaults may change variable precedence expectations → Keep inventory-owned connection variables in group vars and document which values moved.
- Splitting tasks can obscure execution order → Make `tasks/main.yml` an explicit ordered import list.
- Export path expressions depend on `playbook_dir` → Preserve the existing path expression and validate output location after a live run.
- Lint rules may differ for role files → Run syntax check, `yamllint`, and `ansible-lint` against both the entrypoint and role task/default files.
- Behavior-preserving refactors can still change output timing or variable scope → Validate generated YAML/JSON/raw exports against the current expected fields and redaction behavior.

## Migration Plan

1. Create `ansible/roles/switch_readonly_facts/` with defaults, tasks, and a role README.
2. Move workflow defaults from the playbook/group vars into role defaults where appropriate.
3. Move existing playbook tasks into phase-specific role task files without changing task semantics.
4. Replace the body of `readonly-facts.yml` with role invocation while preserving the play target and connection settings.
5. Update switch documentation to describe the role and validation commands.
6. Run static validation and live read-only validation against `sw-core` with raw export enabled.

Rollback is to restore the previous single-file playbook and group vars. Because this is a read-only refactor, rollback does not require device configuration changes.

## Open Questions

- Should `network-cli-smoke.yml` remain a separate playbook or also invoke a lightweight role task path in the future? For this change, keep it separate.
