# Switch Playbooks

These playbooks collect read-only facts from the `SW_CORE` SKS8300-12X switch over encrypted SSH using Ansible `network_cli`. SSH credentials are supplied at runtime and must not be committed.

Run commands from the `ansible/` directory.

## Workflow layout

The `readonly-facts.yml` entrypoint collects facts through the
`roles/switch_readonly_facts/` provider role, then runs a playbook-owned export
workflow:

- `roles/switch_readonly_facts/defaults/main.yml`
- `roles/switch_readonly_facts/tasks/main.yml`
- `roles/switch_readonly_facts/tasks/validate.yml`
- `roles/switch_readonly_facts/tasks/plan.yml`
- `roles/switch_readonly_facts/tasks/collect.yml`
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
The playbook sets `ansible_network_os: cisco.ios.ios` only as a terminal adapter for this SKS8300-12X prompt. Do not use Cisco IOS configuration/resource modules or `cli_config` for this workflow.

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

Only `terminal length 0` is supported for pagination setup. Do not add fallback pagination commands such as `screen-rows per-page 0`.

Safety boundary:

- The role builds and validates the command plan from the selected profile and gather subsets before command collection.
- It does not enter configuration mode.
- It does not create export directories or write files; file persistence is owned by `playbooks/switches/tasks/export-readonly-facts.yml`.
- The profile rejects non-read-only command definitions and mutating command prefixes including `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, and `format`.
- Raw `show running-config` output is redacted in the role-generated export plan before the playbook export workflow saves it.

The design follows the MikroTik-style separation of concerns: gather subsets are
the user-facing fact selector, the SKS8300 command catalog owns CLI strings and
export policy, the profile core in `module_utils/switch_profiles/` owns parsing
and redaction, and future configuration resources should use a separate workflow
rather than this read-only facts role.

Export options are defined at playbook scope and can be overridden at runtime:

```bash
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"],"switch_export_save_raw":true}'
```

Smoke-test and validation commands:

```bash
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
uv run yamllint inventories/homelab.yml inventories/group_vars/switches.yml roles/switch_readonly_facts/defaults/main.yml roles/switch_readonly_facts/tasks/main.yml roles/switch_readonly_facts/tasks/validate.yml roles/switch_readonly_facts/tasks/plan.yml roles/switch_readonly_facts/tasks/collect.yml roles/switch_readonly_facts/tasks/parse.yml playbooks/switches/readonly-facts.yml playbooks/switches/tasks/export-readonly-facts.yml
uv run ansible-lint playbooks/switches/readonly-facts.yml roles/switch_readonly_facts
uv run python -m compileall filter_plugins module_utils
op run --env-file ../.env.switch.tpl -- uv run ansible-playbook playbooks/switches/network-cli-smoke.yml
```

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
