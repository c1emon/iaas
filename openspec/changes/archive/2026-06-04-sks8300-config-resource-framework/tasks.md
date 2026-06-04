## 1. Role and Safety Defaults

- [x] 1.1 Create a future `ansible/roles/switch_config/` structure with defaults, task phase files, and role documentation.
- [x] 1.2 Add safe defaults including `switch_platform_profile: sks8300`, `switch_config_apply: false`, and an explicit allowed operations mechanism.
- [x] 1.3 Keep SSH/network connection variables in inventory or runtime variables rather than role defaults.
- [x] 1.4 Document that `switch_readonly_facts` remains non-mutating and separate from `switch_config`.

## 2. Resource Registry Design

- [x] 2.1 Add SKS8300 config resource registry structures under the shared profile core after the read-only profile core exists.
- [x] 2.2 Define initial resource metadata for a narrow first scope, such as VLAN resources with VLAN ID primary keys.
- [x] 2.3 Define field metadata for required, defaulted, read-only, sensitive, and desired-state fields.
- [x] 2.4 Add validation that rejects unsupported resources, unsupported fields, invalid primary keys, and disallowed operations.

## 3. Planning and Diff Lifecycle

- [x] 3.1 Implement current-state collection using SKS8300 profile read commands and parsers rather than duplicating parser logic in the config role.
- [x] 3.2 Implement intent normalization and matching by resource primary key.
- [x] 3.3 Implement diff generation that reports create, update, remove, and no-op decisions without applying by default.
- [x] 3.4 Export a plan/diff report with current state, desired intent, and planned operations while redacting sensitive values.

## 4. Render, Apply, and Verify Lifecycle

- [x] 4.1 Implement command rendering from validated resource diffs, not raw operator command strings.
- [x] 4.2 Add destructive command and forbidden pattern checks for rendered commands before apply.
- [x] 4.3 Gate live mutation behind `switch_config_apply: true` and keep default runs non-mutating.
- [x] 4.4 Implement post-apply verification by re-collecting or inspecting switch state and comparing it to declared intent.
- [x] 4.5 Export apply and verification status in a change report.

## 5. Documentation

- [x] 5.1 Document the declarative intent model and explain why arbitrary config command lists are not the primary interface.
- [x] 5.2 Document the plan/diff/apply/verify lifecycle and default non-mutating behavior.
- [x] 5.3 Document examples for initial supported resources and allowed operations.
- [x] 5.4 Document operational safety expectations, secret redaction, and manual rollback considerations.

## 6. Validation

- [x] 6.1 Run syntax checks for the configuration role and any example playbook once implemented.
- [x] 6.2 Run `yamllint` on new role YAML and documentation examples where applicable.
- [x] 6.3 Run `ansible-lint` on the configuration role and example playbook once implemented.
- [x] 6.4 Validate plan-only behavior does not send mutating commands.
- [x] 6.5 Validate explicit apply and verify behavior against a low-risk live resource only after operator approval.
