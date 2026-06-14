# Switch Playbooks

These playbooks collect read-only facts from the `SW_CORE` SKS8300-12X switch over encrypted SSH using Ansible `network_cli` and the native `c1emon.xikeos` v0.2.x collection. SSH credentials are supplied at runtime and must not be committed.

Run commands from the `ansible/` directory.

Install repository Ansible collections before running switch workflows:

```bash
uv run ansible-galaxy collection install -r requirements.yml
```

This installs the native Galaxy collection `c1emon.xikeos` constrained to the
repository's v0.2.x baseline alongside the other repository collection
dependencies. Ansible collection installation does not install Python packages,
so keep the control environment synchronized with `uv sync` and ensure parser
libraries used by collection-backed facts/resources, including `ttp` and
`textfsm`, are available.

## Workflow layout

The `readonly-facts.yml` entrypoint collects facts through the
`roles/switch_readonly_facts/` provider role, then runs a playbook-owned export
workflow:

- `roles/switch_readonly_facts/defaults/main.yml`
- `roles/switch_readonly_facts/tasks/main.yml`
- `roles/switch_readonly_facts/tasks/validate.yml`
- `roles/switch_readonly_facts/tasks/plan.yml`
- `roles/switch_readonly_facts/tasks/collect.yml` (native `c1emon.xikeos.xikeos_facts`)
- `roles/switch_readonly_facts/tasks/parse.yml` (fact exposure only)
- `playbooks/switches/tasks/export-readonly-facts.yml`

Operator commands stay unchanged.

## `readonly-facts.yml`

Collects collection-native `ansible_net_*` facts and `ansible_network_resources`
from the switch, then the playbook-level export workflow writes exports under:

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

The supported operator interface is collection fact and resource subset selection:

```yaml
switch_readonly_gather_subset:
  - min
switch_readonly_gather_network_resources:
  - interfaces
  - vlans
  - l2_interfaces
  - l3_interfaces
  - lag_interfaces
  - static_routes
  - acls
```

The role passes those selections to `c1emon.xikeos.xikeos_facts` as
`gather_subset` and `gather_network_resources`. The former repository-specific
`switch_facts` schema, command IDs, stdout mapping, and local parser filters are
not part of the normal facts workflow.

Current fact subsets:

- `min`: baseline device facts
- `hardware`: hardware facts when requested
- `config`: redacted configuration facts when requested

Current network resource subsets:

- `interfaces`
- `vlans`
- `l2_interfaces`
- `l3_interfaces`
- `lag_interfaces`
- `static_routes`
- `acls`

Pagination handling is owned by the native XikeOS facts path. Explicit
pagination commands such as `terminal length 0` belong only in separate smoke,
debug, or documented fallback command workflows.

Safety boundary:

- The role validates the selected collection subsets before facts collection.
- It collects through `c1emon.xikeos.xikeos_facts` and does not enter configuration mode.
- It does not create export directories or write files; file persistence is owned by `playbooks/switches/tasks/export-readonly-facts.yml`.
- Normal exports write collection-native facts only. Raw command output export requires a separate smoke, debug, or documented fallback workflow.

The design follows the MikroTik-style separation of concerns: collection subsets
are the user-facing fact/resource selector, the collection owns parsing and
resource state, and configuration resources use a separate workflow rather than
this read-only facts role.

## `config-plan.yml`

The configuration workflow is separate from read-only facts. It validates
collection-native `switch_config_resources` entries and calls lifecycle-safe
native collection modules directly in this deterministic order:

- `vlans` -> `c1emon.xikeos.xikeos_vlans`
- `base_interfaces` -> `c1emon.xikeos.xikeos_interfaces`
- `lag_interfaces` -> `c1emon.xikeos.xikeos_lag_interfaces`
- `l2_interfaces` -> `c1emon.xikeos.xikeos_l2_interfaces`
- `l3_interfaces` -> `c1emon.xikeos.xikeos_l3_interfaces`
- `static_routes` -> `c1emon.xikeos.xikeos_static_routes`
- `acls` -> `c1emon.xikeos.xikeos_acls`

Each resource group contains module call entries with `state` and `config`
fields. The `config` shape is the installed `c1emon.xikeos` module schema, not a
repository-translated alias schema.

`switch_config_apply` remains `false` by default. Plan-only runs execute the
collection modules in check mode and do not send mutating configuration. When
`switch_config_apply=true`, the role invokes the same native modules only after
`switch_config_allowed_states` and destructive-command checks pass. The default
allowed state is `merged`; opt into `deleted` or `replaced` explicitly when a
workflow needs those module states.

Legacy fields are rejected. Migrate `switch_config_intent` to
`switch_config_resources`, VLAN `id` to `vlan_id`, `present`/`absent` to module
states such as `merged`/`deleted`, and local L2 aliases such as `tagged_vlans` or
`untagged_vlans` to the native collection module field names.

Change reports include requested collection-native resources, allowed-state
policy, check-mode preview results, apply results, and apply status. They no
longer include repository-local diff/rendered command planning fields.

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

- `switch_config` maps supported intent to lifecycle-complete v0.2.x resource
  modules for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG
  interfaces, static routes, and ACLs.
- The compatibility SKS8300 parsers are not used by the normal read-only facts
  or configuration current-state workflows.
- `xikeos_config` remains a documented fallback only for future unsupported gaps;
  it is not invoked by the repository workflow.

## Migration for direct role callers

`switch_readonly_facts` no longer writes files from inside the role. Direct role
callers now receive in-memory collection-native facts only. To keep file
exports, define caller-owned export variables such as `switch_export_formats`,
`switch_export_dir`, and `switch_raw_output_dir`, then run equivalent copy/file
tasks after the role. The switch playbook's
`tasks/export-readonly-facts.yml` file can be reused as a reference workflow.

After a live run, verify the generated `facts.yml` or `facts.json` contains:

- collection-provided `ansible_net_*` keys such as model/version/serial fields
- `ansible_network_resources.vlans`
- `ansible_network_resources.interfaces` and related L2/L3/LAG resource keys when requested

Normal facts export does not write raw command output. If a separately documented
fallback raw export is introduced, verify it redacts plaintext local user
passwords, RADIUS/TACACS secrets, and SNMP communities.

VLAN write/configuration management is out of scope for this read-only facts workflow, even though limited `cli_command` write testing was performed during discovery.
