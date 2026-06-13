# Switch Playbooks

These playbooks collect read-only facts from the `SW_CORE` SKS8300-12X switch over encrypted SSH using Ansible `network_cli` and the native `c1emon.xikeos` collection. SSH credentials are supplied at runtime and must not be committed.

Run commands from the `ansible/` directory.

Install repository Ansible collections before running switch workflows:

```bash
uv run ansible-galaxy collection install -r requirements.yml
```

This installs the native Galaxy collection `c1emon.xikeos` alongside the other
repository collection dependencies. Ansible collection installation does not
install Python packages, so keep the control environment synchronized with
`uv sync` and ensure parser libraries used by collection-backed facts/resources,
including `ttp` and `textfsm`, are available.

## Workflow layout

The `readonly-facts.yml` entrypoint collects facts through the
`roles/switch_readonly_facts/` provider role, then runs a playbook-owned export
workflow:

- `roles/switch_readonly_facts/defaults/main.yml`
- `roles/switch_readonly_facts/tasks/main.yml`
- `roles/switch_readonly_facts/tasks/validate.yml`
- `roles/switch_readonly_facts/tasks/plan.yml`
- `roles/switch_readonly_facts/tasks/collect.yml` (native `c1emon.xikeos.xikeos_command`)
- `roles/switch_readonly_facts/tasks/parse.yml`
- `playbooks/switches/tasks/export-readonly-facts.yml`

Operator commands stay unchanged.

## `readonly-facts.yml`

Collects version and VLAN facts from the switch, parses them into structured
output, and then the playbook-level export workflow writes exports under:

```text
exports/switches/<inventory_hostname>/
```

Runtime secrets are injected with 1Password CLI, matching the OPNsense playbook pattern:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml
```

The template maps:

```text
SWITCH_SSH_USER=op://Astra/SW_CORE/username
SWITCH_SSH_PASSWORD=op://Astra/SW_CORE/password
SWITCH_SSH_PORT=22
```

Adjust `.env.switch.tpl` if the 1Password item or field names differ.

The Ansible control environment uses `paramiko` as the Python SSH backend for `network_cli`.
Switch inventory and playbooks set `ansible_network_os: c1emon.xikeos.xikeos` so
terminal and cliconf behavior comes from the native XikeOS collection. Do not use
the former Cisco IOS terminal adapter, Cisco IOS configuration/resource modules,
or generic `cli_config` for this workflow.

The supported operator interface is profile and gather-subset selection:

```yaml
switch_platform_profile: sks8300
switch_readonly_gather_subset:
  - device
  - vlans
  - interfaces
```

The `sks8300` profile expands those fact subsets into the approved read-only
command catalog. Do not override command lists directly; add SKS8300 commands
to the profile catalog and subset registry when new facts are needed.

Current subsets:

- `default`: always included for setup behavior such as pagination handling
- `device`: device identity/version facts from `show version`
- `vlans`: VLAN facts from VLAN tables and redacted running config parsing
- `interfaces`: interface VLAN membership facts from running config parsing

Only `terminal length 0` is supported for pagination setup when the compatibility
profile needs explicit pagination handling. Do not add fallback pagination
commands such as `screen-rows per-page 0`.

Safety boundary:

- The role builds and validates the command plan from the selected profile and gather subsets before command collection.
- It collects through `c1emon.xikeos.xikeos_command` and does not enter configuration mode.
- It does not create export directories or write files; file persistence is owned by `playbooks/switches/tasks/export-readonly-facts.yml`.
- The profile rejects non-read-only command definitions and mutating command prefixes including `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, and `format`.
- Raw `show running-config` output is redacted in the role-generated export plan before the playbook export workflow saves it.

The design follows the MikroTik-style separation of concerns: gather subsets are
the user-facing fact selector, the SKS8300 command catalog owns CLI strings and
export policy, the profile core in `module_utils/switch_profiles/` owns parsing
and redaction, and future configuration resources should use a separate workflow
rather than this read-only facts role.

## `config-plan.yml`

The configuration workflow is separate from read-only facts. It validates
declarative `switch_config_intent`, collects current state through
`c1emon.xikeos.xikeos_command`, computes the repository diff/report, and maps
supported resources to lifecycle-safe native collection modules:

- VLAN create/update/remove intent maps to `c1emon.xikeos.xikeos_vlans` with
  `merged` or `deleted` states.
- L2 interface access, trunk, and hybrid intent maps to
  `c1emon.xikeos.xikeos_l2_interfaces` with `merged` state.
- Unsupported interface/resource gaps fail before apply and must be documented
  before any fallback is added.

`switch_config_apply` remains `false` by default. Plan-only runs may execute
collection check-mode previews and current-state gathering, but do not send
mutating configuration. When `switch_config_apply=true`, the role invokes native
collection resource modules only after `switch_config_allowed_operations` and
destructive-command checks pass. The repository does not use
`c1emon.xikeos.xikeos_config` as the primary declarative interface; raw config is
reserved for future, explicitly documented gaps and must keep the same allowed
operation and destructive-command guardrails.

Change reports continue to include current state, desired intent, repository
diff/rendered command summaries, native collection module previews/results,
apply status, and verification outcome.

Export options are defined at playbook scope and can be overridden at runtime:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"],"switch_export_save_raw":true}'
```

Smoke-test and validation commands:

```bash
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
uv run ansible-playbook --syntax-check playbooks/switches/config-plan.yml
uv run yamllint inventories/homelab.yml inventories/group_vars/switches.yml roles/switch_readonly_facts/defaults/main.yml roles/switch_readonly_facts/tasks/main.yml roles/switch_readonly_facts/tasks/validate.yml roles/switch_readonly_facts/tasks/plan.yml roles/switch_readonly_facts/tasks/collect.yml roles/switch_readonly_facts/tasks/parse.yml playbooks/switches/readonly-facts.yml playbooks/switches/tasks/export-readonly-facts.yml
uv run ansible-lint playbooks/switches/readonly-facts.yml roles/switch_readonly_facts playbooks/switches/config-plan.yml roles/switch_config
uv run python -m unittest tests/test_xikeos_migration.py
uv run python -m compileall filter_plugins module_utils
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/network-cli-smoke.yml
```

Live validation should start with `network-cli-smoke.yml` and
`readonly-facts.yml`. Do not run apply-enabled `config-plan.yml` until those
read-only native XikeOS collection paths pass against the target switch.

## Current native collection gaps and follow-up notes

- `switch_config` currently maps VLAN intent to `xikeos_vlans` and L2
  access/trunk/hybrid interface intent to `xikeos_l2_interfaces` only.
- Base interface, L3 interface, and LAG resource modules exist in the collection
  but are not exposed through this repository's `switch_config_intent` schema yet.
- The compatibility SKS8300 parsers remain in use to preserve the existing
  `switch_facts` output shape and verification behavior until equivalent native
  gathered resource schemas are validated live.
- `xikeos_config` remains a documented fallback only for future unsupported gaps;
  it is not invoked by the repository workflow.

## Migration for direct role callers

`switch_readonly_facts` no longer writes files from inside the role. Direct role
callers now receive in-memory facts and export-plan variables only. To keep file
exports, define caller-owned export variables such as `switch_export_formats`,
`switch_export_save_raw`, `switch_export_dir`, and `switch_raw_output_dir`, then
run equivalent copy/file tasks after the role. The switch playbook's
`tasks/export-readonly-facts.yml` file can be reused as a reference workflow.

After a live run, verify the generated `facts.yml` or `facts.json` contains:

- `device.model`, `device.software_version`, `device.bootrom_version`, serial/MAC, and uptime fields from `show version`
- VLAN entries under `vlans`
- interface membership under `interfaces` with numeric `allowed_vlans`, `tagged_vlans`, and `untagged_vlans` lists

If `switch_export_save_raw=true`, verify `raw-output/show-running-config.txt` contains no plaintext local user passwords, RADIUS/TACACS secrets, or SNMP communities.

VLAN write/configuration management is out of scope for this read-only facts workflow, even though limited `cli_command` write testing was performed during discovery.
