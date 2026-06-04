# switch_config

Declarative SKS8300 configuration planning and application role.

This role is separate from `switch_readonly_facts`. The read-only facts role
remains non-mutating: it only validates, plans approved show commands, collects
CLI output, and parses facts. Configuration changes require this role and its
explicit apply gate.

## Intent model

Operators declare supported resources instead of raw CLI command lists. The
profile core validates the intent, collects current state with read-only profile
commands, computes an idempotent diff, renders candidate commands from resource
metadata, and exports a redacted change report.

Raw arbitrary command lists such as `switch_config_commands` are rejected because
they bypass validation, idempotency, audit, and safety checks.

Initial supported resource scope:

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
```

VLAN resources use `id` as the primary key. Supported VLAN fields are `id`,
`name`, and `state`. Read-only and sensitive field metadata lives in
`ansible/module_utils/switch_profiles/sks8300/resources.py`.

## Lifecycle

1. validate runtime inputs and reject raw command lists
2. collect current state using SKS8300 read-only command planning and parsers
3. normalize intent and match resources by primary key
4. compute create/update/remove/no-op diffs
5. render candidate commands from validated resource diffs
6. block forbidden destructive patterns before apply
7. apply only when `switch_config_apply: true`
8. re-collect state and verify intent after apply
9. export `switch_config_change_report`

By default `switch_config_apply` is `false`, so the role produces a plan/diff and
does not send mutating commands.

## Runtime variables

Connection and credential variables stay in inventory or runtime variables, not
role defaults. Provide values such as `ansible_user`, `ansible_password`,
`ansible_port`, `ansible_connection`, and `ansible_network_os` outside this role.

## Safety and rollback

Allowed operations are controlled by `switch_config_allowed_operations`. Rendered
commands are checked for destructive patterns such as `reload`, `erase`,
`delete startup-config`, and `write erase` before apply. Reports redact fields
marked sensitive by the resource registry.

Rollback is manual or plan-based for the initial framework. Review the rendered
command summaries and change report before enabling live apply, and validate live
changes only on low-risk resources with operator approval.
