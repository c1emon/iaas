# switch_config

Repository safety orchestration for collection-native SKS8300/XikeOS
configuration preview and application.

This role keeps configuration policy separate from the native collection
resource modules. It remains non-mutating unless `switch_config_apply: true` is
set.

## Resource input contract

Operators declare grouped `switch_config_resources` entries. Each entry is a
direct call shape for the corresponding lifecycle-complete `c1emon.xikeos`
resource module: it must include a module `state` and module `config` list.

```yaml
switch_config_apply: false
switch_config_allowed_states:
  - merged
switch_config_resources:
  vlans:
    - state: merged
      config:
        - vlan_id: 10
          name: users
    - state: deleted
      config:
        - vlan_id: 999
  l2_interfaces:
    - state: merged
      config:
        - name: Ethernet1/0/3
          mode: access
          access_vlan: 10
```

Supported resource groups and modules, in execution order:

1. `vlans` -> `c1emon.xikeos.xikeos_vlans`
2. `base_interfaces` -> `c1emon.xikeos.xikeos_interfaces`
3. `lag_interfaces` -> `c1emon.xikeos.xikeos_lag_interfaces`
4. `l2_interfaces` -> `c1emon.xikeos.xikeos_l2_interfaces`
5. `l3_interfaces` -> `c1emon.xikeos.xikeos_l3_interfaces`
6. `static_routes` -> `c1emon.xikeos.xikeos_static_routes`
7. `acls` -> `c1emon.xikeos.xikeos_acls`

Rendered-only v0.2.x collection resources such as STP, ERPS, EAPS, QinQ,
mirror, port isolation, flex monitor link, and OSPF v2 are not accepted by this
role. Use a separately documented fallback workflow until lifecycle-complete
collection modules exist for those features.

## Validation and policy

The role rejects:

- legacy `switch_config_intent`
- raw arbitrary command lists such as `switch_config_commands`
- unknown resource group keys
- resource calls without `state` and `config`
- states outside `switch_config_allowed_states`

`switch_config_allowed_states` is the repository-owned safety policy. The
default allows only `merged`; operators must explicitly opt into states such as
`deleted` or `replaced` before the role will preview or apply those calls.
With the v0.2.1 collection baseline, L3 interface and LAG `merged` operations
are additive: omitted addresses or LAG members are not interpreted as removals.

## Lifecycle

1. validate runtime network settings and collection-native resource variables
2. invoke configured collection resource modules in check mode for preview
3. reject destructive command summaries such as `reload`, `erase`,
   `delete startup-config`, or `write erase`
4. apply the same static module calls only when `switch_config_apply: true`
5. export `switch_config_change_report`

The collection modules own argspec validation, resource identity, diffing,
command generation, before/after state, apply, and verification. This repository
keeps only safety orchestration policy: apply gate, allowed states,
deterministic module ordering, destructive-command checks, and redacted report
aggregation.

## Migration from legacy intent fields

The prior repository-local intent model is removed. Migrate values to the native
collection module schemas:

- `switch_config_intent` -> `switch_config_resources`
- VLAN `id` -> `vlan_id`
- `state: present` -> call `state: merged`
- `state: absent` -> call `state: deleted` and allow `deleted` in
  `switch_config_allowed_states`
- interface `interfaces` alias -> use the appropriate native group, usually
  `l2_interfaces` or `base_interfaces`
- `tagged_vlans` -> collection field such as `trunk_allowed_vlan`
- `untagged_vlans` -> collection L2 interface schema field supported by the
  installed `c1emon.xikeos` version

Connection and credential variables stay in inventory or runtime variables, not
role defaults. Provide `ansible_user`, `ansible_password`, `ansible_port`,
`ansible_connection`, and `ansible_network_os` outside this role.
