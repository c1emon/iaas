# switch_readonly_facts

Side-effect-free read-only native facts provider for SKS8300/XikeOS-series switches.

The role validates inputs, calls `c1emon.xikeos.xikeos_facts` over
`network_cli`, and exposes collection-native structured facts. It does not
create directories or write export files. Callers that want persistence should
run a separate playbook-level export workflow after the role completes.
Inventory and playbooks use `ansible_network_os: c1emon.xikeos.xikeos` with
`ansible.netcommon.network_cli`.

Supported user-facing inputs:

```yaml
switch_readonly_gather_subset:
  - min
switch_readonly_gather_network_resources:
  - vlans
  - interfaces
  - l2_interfaces
  - l3_interfaces
  - lag_interfaces
  - static_routes
  - acls
```

Do not override raw CLI command lists for this role. Normal fact selection maps
directly to `xikeos_facts.gather_subset` and
`xikeos_facts.gather_network_resources`. Use `xikeos_command` only in separate
smoke, debug, or explicitly documented fallback workflows.

Phases:

- validate runtime credentials and guardrails
- build a collection-native `xikeos_facts` request
- collect native facts over `network_cli` with `c1emon.xikeos.xikeos_facts`
- expose `ansible_net_*` facts and `ansible_network_resources` to caller-owned tasks

Output variables:

- `switch_xikeos_facts_module`: collection facts module name
- `switch_xikeos_gather_subset`: requested collection fact subsets
- `switch_xikeos_gather_network_resources`: requested collection resource subsets
- `switch_native_facts`: collection-provided Ansible facts, including `ansible_net_*`
- `switch_network_resources`: collection-provided `ansible_network_resources`

Migration note: callers that previously relied on this role to write
`facts.yml`, `facts.json`, `README.md`, or `raw-output/*` should import or copy a
caller-owned export task file after the role. The switch playbook uses
`playbooks/switches/tasks/export-readonly-facts.yml` for that purpose.

This keeps read-only facts separate from configuration resources: collection
subsets select facts and resources, file persistence stays caller-owned, and
the former repository-specific `switch_facts` schema is no longer emitted by the
normal workflow.
