# switch_config

Declarative SKS8300/XikeOS configuration planning and application role.

This role is separate from `switch_readonly_facts`. The read-only facts role
remains non-mutating: it only validates, plans approved show commands, collects
CLI output, and parses facts. Configuration changes require this role and its
explicit apply gate.

## Intent model

Operators declare supported resources instead of raw CLI command lists. The
profile core validates the intent, collects current state with native
`c1emon.xikeos.xikeos_command` read-only operations, computes an idempotent diff,
maps supported resources to lifecycle-safe `c1emon.xikeos` modules, and exports a
redacted change report.

Raw arbitrary command lists such as `switch_config_commands` are rejected because
they bypass validation, idempotency, audit, and safety checks.

Supported resource scope:

```yaml
switch_platform_profile: sks8300
switch_config_apply: false
switch_config_allowed_operations:
  - create
  - update
  - remove
  - no-op
switch_config_intent:
  vlans:
    - id: 10
      name: users
      state: present
    - id: 999
      state: absent
  interfaces:
    - name: Ethernet1/0/3
      mode: access
      access_vlan: 10
    - name: Ethernet1/0/4
      mode: trunk
      tagged_vlans: [10, 20, 50]
    - name: Ethernet1/0/5
      mode: hybrid
      tagged_vlans: [10, 20]
      untagged_vlans: [99]
```

VLAN resources use `id` as the primary key and map to
`c1emon.xikeos.xikeos_vlans` (`merged` for create/update and `deleted` for
remove). Supported VLAN fields are `id`, `name`, and `state`. Read-only and
sensitive field metadata lives in `ansible/module_utils/switch_profiles/sks8300/resources.py`.

Interface resources use `name` as the primary key, reuse the `interfaces`
collect subset from the read-only SKS8300 parser, and map supported access,
trunk, and hybrid L2 intent to `c1emon.xikeos.xikeos_l2_interfaces`. Supported
interface fields are:

- `name`: required SKS8300 Ethernet-style port name, such as `Ethernet1/0/3`
- `mode`: `access`, `trunk`, or `hybrid`
- `access_vlan`: access VLAN ID for `mode: access`
- `tagged_vlans`: desired tagged VLAN ID list for trunk/hybrid ports
- `untagged_vlans`: desired untagged VLAN ID list for hybrid ports
- `state`: only `present` is supported for interfaces

Mode-specific validation is strict: access ports require `access_vlan` and reject
tagged or untagged lists, trunk ports accept tagged VLANs only, and hybrid ports
accept tagged and/or untagged VLAN lists. Unsupported fields and raw command
strings are rejected before any commands are rendered.

## Lifecycle

1. validate runtime inputs and reject raw command lists
2. collect current state using native XikeOS read-only command operations and compatibility parsers
3. normalize intent and match resources by primary key
4. compute create/update/remove/no-op diffs
5. render candidate command summaries and native collection module operation payloads
6. block forbidden destructive patterns in rendered summaries and collection module outputs before apply
7. run collection modules in check mode for preview
8. apply through collection resource modules only when `switch_config_apply: true`
9. re-collect state and verify intent after apply
10. export `switch_config_change_report`

By default `switch_config_apply` is `false`, so the role produces a plan/diff and
does not send mutating commands.

Interface changes are higher risk than VLAN definition changes because they can
disconnect hosts or uplinks. Always review the rendered commands and redacted
change report before setting `switch_config_apply: true` for interface intent.

## Runtime variables

Connection and credential variables stay in inventory or runtime variables, not
role defaults. Provide values such as `ansible_user`, `ansible_password`,
`ansible_port`, `ansible_connection`, and `ansible_network_os` outside this role.

## Safety and rollback

Allowed operations are controlled by `switch_config_allowed_operations`. Rendered
commands and native collection module command outputs are checked for destructive
patterns such as `reload`, `erase`, `delete startup-config`, and `write erase`
before apply. Reports redact fields marked sensitive by the resource registry.
`c1emon.xikeos.xikeos_config` is not the primary workflow interface; any future
raw configuration fallback must be documented as a resource gap and keep these
same allowlist and destructive-command guardrails.

Rollback is manual or plan-based for the initial framework. Review the rendered
command summaries and change report before enabling live apply, and validate live
changes only on low-risk resources with operator approval.

For interface validation, choose an unused or otherwise low-risk port, capture the
existing parsed state and rendered rollback intent before applying, verify the
post-state, and manually restore the previous port configuration immediately
after the test. Do not use production, uplink, management, or unknown ports for
first validation.
