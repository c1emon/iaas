# Switch Playbooks

These playbooks collect read-only facts directly with
`c1emon.xikeos.xikeos_facts` and use `switch_config` as the repository safety
orchestration layer for native collection configuration previews and apply.

Run commands from the `automation/ansible/` directory.

Install repository Ansible collections before running switch workflows:

```bash
uv run ansible-galaxy collection install -r requirements.yml
```

This installs the native Galaxy collection `c1emon.xikeos` constrained to the
repository's v0.2.1+ baseline alongside the other repository collection
dependencies. Ansible collection installation does not install Python packages,
so keep the control environment synchronized with `uv sync` and ensure parser
libraries used by collection-backed facts/resources, including `ttp` and
`textfsm`, are available.

## `readonly-facts.yml`

The supported read-only entrypoint validates runtime SSH settings, prepares the
gather subset/resource inputs, calls `c1emon.xikeos.xikeos_facts` directly, and
then runs the playbook-owned export workflow. The former
`switch_readonly_facts` role has been removed because it only wrapped this
single collection facts call.

Custom callers can use the direct collection fallback: call
`c1emon.xikeos.xikeos_facts` directly with inventory/runtime connection
variables, then reuse the export task shape from
`playbooks/switches/tasks/export-readonly-facts.yml` if file output is needed.

Structured exports are written under:

```text
exports/switches/<inventory_hostname>/
```

Runtime secrets are injected with 1Password CLI, matching the OPNsense playbook pattern:

```bash
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml
```

The template maps:

```text
SWITCH_SSH_USER=op://Astra/SW_CORE/username
SWITCH_SSH_PASSWORD=op://Astra/SW_CORE/password
SWITCH_SSH_PORT=22
```

Adjust `.env.switch.tpl` if the 1Password item or field names differ.

The Ansible control environment uses `paramiko` as the Python SSH backend for
`network_cli`. Switch inventory and playbooks set
`ansible_network_os: c1emon.xikeos.xikeos` so terminal and cliconf behavior
comes from the native XikeOS collection. Do not use the former Cisco IOS
terminal adapter, Cisco IOS configuration/resource modules, or generic
`cli_config` for this workflow.

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

The playbook passes those selections to `c1emon.xikeos.xikeos_facts` as
`gather_subset` and `gather_network_resources`. The former repository-specific
`switch_facts` schema, command IDs, stdout mapping, and local parser filters are
not part of the normal facts workflow.

Safety boundary:

- The playbook validates the selected collection subsets before facts collection.
- It collects through `c1emon.xikeos.xikeos_facts` and does not enter configuration mode.
- It does not create export directories or write files during facts collection;
  file persistence is owned by `playbooks/switches/tasks/export-readonly-facts.yml`.
- Normal exports write collection-native facts only. Raw command output export
  requires a separate smoke, debug, or documented fallback workflow.

## `config-plan.yml`

The configuration workflow is separate from read-only facts. It keeps
`switch_config` as the repository-owned safety orchestration role, validates
collection-native `switch_config_resources` entries, and calls lifecycle-safe
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
workflow needs those module states. With the v0.2.1 collection baseline, L3 and
LAG `merged` calls are additive: omitted addresses or LAG members are not treated
as removals.

Legacy fields are rejected. Migrate `switch_config_intent` to
`switch_config_resources`, VLAN `id` to `vlan_id`, `present`/`absent` to module
states such as `merged`/`deleted`, and local L2 aliases such as `tagged_vlans`
or `untagged_vlans` to the native collection module field names.

Change reports include requested collection-native resources, allowed-state
policy, check-mode preview results, apply results, and apply status. They no
longer include repository-local diff/rendered command planning fields.

Export options are defined at playbook scope and can be overridden at runtime:

```bash
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- uv run ansible-playbook playbooks/switches/readonly-facts.yml \
  -e '{"switch_export_formats":["yaml","json"],"switch_export_save_raw":true}'
```

Smoke-test and validation commands:

```bash
uv run ansible-playbook --syntax-check playbooks/switches/readonly-facts.yml
uv run ansible-playbook --syntax-check playbooks/switches/config-plan.yml
uv run yamllint ../../environments/astra/ansible/inventory.yml ../../environments/astra/ansible/group_vars/switches.yml playbooks/switches/readonly-facts.yml playbooks/switches/tasks/export-readonly-facts.yml playbooks/switches/config-plan.yml roles/switch_config/defaults/main.yml roles/switch_config/tasks/main.yml roles/switch_config/tasks/validate.yml roles/switch_config/tasks/diff.yml roles/switch_config/tasks/apply.yml roles/switch_config/tasks/export.yml
uv run ansible-lint playbooks/switches/readonly-facts.yml playbooks/switches/config-plan.yml roles/switch_config
uv run pytest ../../tests/ansible/test_xikeos_migration.py
uv run python -m compileall module_utils
op run --env-file ../../environments/astra/runtime/.env.switch.tpl -- uv run ansible-playbook playbooks/switches/network-cli-smoke.yml
```

Live validation should start with `network-cli-smoke.yml` and
`readonly-facts.yml`. Do not run apply-enabled `config-plan.yml` until those
read-only native XikeOS collection paths pass against the target switch.

## Current native collection gaps and follow-up notes

- `switch_config` maps supported intent to lifecycle-complete v0.2.1+ resource
  modules for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG
  interfaces, static routes, and ACLs.
- The compatibility SKS8300 parsers are not used by the normal read-only facts
  or configuration current-state workflows.
- `xikeos_config` remains a documented fallback only for future unsupported gaps;
  it is not invoked by the repository workflow.
