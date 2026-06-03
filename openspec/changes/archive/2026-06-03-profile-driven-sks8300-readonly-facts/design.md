## Context

The SKS8300 read-only facts workflow has already moved toward a role boundary, but its behavior is still defined by a user-visible fixed CLI command list. That makes the workflow hard to extend because adding SKS8300-series data such as LLDP, MAC table, STP, PoE, or transceiver facts would require expanding command defaults and role assertions instead of selecting higher-level fact groups.

MikroTik/RouterOS Ansible designs provide useful patterns for this next step: facts are selected by gather subsets, raw command execution is separate from declarative workflows, and reusable module utilities hold the device-specific schema and transformation logic. The SKS8300 workflow should borrow these patterns without becoming a custom Ansible collection in this change.

## Goals / Non-Goals

**Goals:**

- Treat `sks8300` as a platform/series profile, not a `sw-core` host-specific profile.
- Replace user-facing read-only CLI command variables with `switch_platform_profile` and `switch_readonly_gather_subset`.
- Add an explicit command planning phase to `switch_readonly_facts` before CLI collection.
- Keep the Ansible filter plugin layer thin and move profile-specific command planning, parser dispatch, redaction, and raw export policy into `ansible/module_utils/switch_profiles/`.
- Preserve current SSH `network_cli` transport, terminal adapter behavior, structured facts schema, export paths, and redaction outcomes.
- Design the Python package layout so a later configuration resource framework can reuse the SKS8300 profile without sharing the read-only role entrypoint.

**Non-Goals:**

- Do not add switch configuration mutation, config apply, VLAN write management, or arbitrary command execution.
- Do not convert the local Ansible layout into a published collection.
- Do not add a custom Ansible module in this change.
- Do not introduce support for non-SKS8300 platforms.
- Do not preserve `switch_cli_commands` as a user-supported compatibility interface.

## Decisions

### Use `switch_platform_profile` plus `switch_readonly_gather_subset`

The operator-facing model should become:

```yaml
switch_platform_profile: sks8300
switch_readonly_gather_subset:
  - default
  - device
  - vlans
  - interfaces
```

This mirrors the MikroTik facts `gather_subset` style while keeping the profile name explicit. `switch_platform_profile` describes how the device family speaks and parses; inventory remains responsible for host identity, connection address, credentials, and instance-specific metadata.

Alternative considered: keep `switch_readonly_fact_sets`. Rejected because `gather_subset` is more recognizable to Ansible network users and maps naturally to facts behavior.

Alternative considered: profile name `sw_core_sks8300`. Rejected because the adapter should target the SKS8300 model/series and keep host-specific quirks in inventory variables.

### Keep roles as workflow owners and Python as profile engine

The role remains responsible for validation, planning, collection, parsing orchestration, and export. Python owns SKS8300 profile semantics.

Target role layout:

```text
roles/switch_readonly_facts/tasks/
  main.yml
  validate.yml
  prepare.yml
  plan.yml
  collect.yml
  parse.yml
  export.yml
```

`plan.yml` calls a filter to build the command plan. `collect.yml` loops over the planned commands. `parse.yml` maps CLI results to command IDs and asks the profile to build facts.

Alternative considered: keep all command planning in YAML defaults. Rejected because command sensitivity, subset expansion, parser dispatch, and future version handling are easier to validate and test in Python.

### Use a thin filter facade over `module_utils`

Ansible-facing Jinja filters should live in `ansible/filter_plugins/switch_profiles.py` and should be limited to stable facade functions such as:

- `switch_read_command_plan(gather_subset, profile)`
- `switch_cli_output_map(command_plan, cli_results)`
- `switch_parse_facts(outputs, profile, gather_subset, inventory_hostname)`
- `switch_raw_export_plan(command_plan, outputs, profile)`

The actual implementation should live under:

```text
ansible/module_utils/switch_profiles/
  registry.py
  read.py
  errors.py
  common.py
  sks8300/
    profile.py
    commands.py
    read_subsets.py
    parsers.py
    redaction.py
```

This follows the MikroTik pattern where module/filter entrypoints are relatively thin and `module_utils` carries shared device logic.

Alternative considered: keep parser and profile logic in `filter_plugins/switch_cli_facts.py`. Rejected because that would keep growing a filter plugin into the adapter engine and make later config-resource reuse awkward.

### Model SKS8300 read facts as subset classes or registry entries

The SKS8300 profile should define gather subsets such as:

- `default`: always-required base subset and/or common setup behavior
- `device`: version and hardware identity facts
- `vlans`: VLAN definitions and VLAN tables
- `interfaces`: interface mode and VLAN membership facts

Each subset maps to command IDs from a command catalog and parser functions. Command IDs map to CLI strings and policy metadata such as `read_only`, `sensitive`, and `raw_export`.

Alternative considered: expose command IDs directly to users. Rejected because the workflow should remain fact-oriented and should not become a raw command runner.

### Preserve read/write separation for future config work

This change should leave room for later SKS8300 config resources but must not implement them. A future `switch_config` role can reuse `module_utils/switch_profiles/sks8300/` while exposing an intent/diff/apply/verify workflow separate from read-only facts.

Alternative considered: add config operation stubs now. Rejected because unused config stubs would expand scope and invite premature design around unimplemented mutation behavior.

## Risks / Trade-offs

- Breaking variable model may surprise callers using `switch_cli_commands` → Document the migration to `switch_readonly_gather_subset` and remove the command override examples.
- Moving parser code can change import/discovery behavior → Keep a thin filter facade and run syntax, lint, parser unit-style checks where available, and live `sw-core` validation.
- `module_utils` imports from local filter plugins can be brittle outside a collection → Use Ansible-supported `ansible.module_utils...` import paths and validate from `ansible/` with the existing config.
- Gather subset expansion can accidentally duplicate commands → Deduplicate command plans by command ID while preserving setup command ordering.
- Sensitive raw export policy can regress during refactor → Keep `show_running_config` as `redacted_only` and verify raw export files after a live run.

## Migration Plan

1. Introduce `switch_platform_profile: sks8300` and `switch_readonly_gather_subset` defaults in the role.
2. Add the SKS8300 profile package under `ansible/module_utils/switch_profiles/` using existing parser and redaction behavior.
3. Add `ansible/filter_plugins/switch_profiles.py` as the Ansible-facing facade.
4. Add `tasks/plan.yml` to the role and change collection to loop over the profile command plan.
5. Change parsing/export tasks to consume command IDs and raw export policy from the command plan.
6. Remove user-facing command-list defaults and update validation and documentation.
7. Run static validation and live role-backed validation against `sw-core` with raw export enabled.

Rollback is to restore the role defaults and tasks to the fixed command-list model from the previous role refactor. Because this remains read-only, rollback does not require switch configuration changes.

## Open Questions

- Should `default` be always included like MikroTik facts, or should defaults explicitly list every subset? The initial design should favor `default` always included for base setup behavior while keeping exported facts controlled by requested subsets.
- Should future parser tests use saved CLI fixtures under `ansible/tests/fixtures/` or lightweight Python unit tests outside Ansible? This can be decided during implementation if no current test harness exists.
