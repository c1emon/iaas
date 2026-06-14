## Why

The switch roles were originally useful while this repository carried local
SKS8300 profile parsing, resource planning, and collection-like behavior. Now
that `c1emon.xikeos` owns XikeOS terminal behavior, facts, resource schemas,
check-mode previews, diffs, apply, and lifecycle results, the remaining role
layer should be reduced to repository policy or removed where it only wraps a
single collection module call.

## What Changes

- Reassess `ansible/roles/switch_readonly_facts` and inline it into
  `playbooks/switches/readonly-facts.yml` if it only validates and calls
  `c1emon.xikeos.xikeos_facts` without adding reusable policy.
- Keep switch facts export as a playbook-owned workflow, not a role side effect.
- Reassess `ansible/roles/switch_config` and either keep it as a clearly named
  repository safety/orchestration role or collapse repetitive module dispatch
  into playbook-level tasks if the role no longer provides enough abstraction.
- Preserve repository-owned guardrails if configuration orchestration remains:
  explicit apply gate, allowed-state policy, deterministic module ordering,
  destructive-command checks, no raw command interface, and redacted reporting.
- Remove stale role documentation and tests that imply repository-local platform,
  facts, or resource implementation.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `switch-cli-readonly-facts`: Clarify whether read-only switch facts require a
  reusable role or can be collected directly by the playbook through
  `c1emon.xikeos.xikeos_facts`.
- `switch-readonly-facts-export-workflow`: Preserve caller-owned export behavior
  if the read-only facts role is removed or reduced.
- `sks8300-config-resource-framework`: Clarify that any remaining configuration
  role is repository policy/orchestration only, not a platform/resource
  implementation layer.

## Impact

- Affected roles: `ansible/roles/switch_readonly_facts/` and
  `ansible/roles/switch_config/`.
- Affected playbooks: `ansible/playbooks/switches/readonly-facts.yml`,
  `ansible/playbooks/switches/config-plan.yml`, and
  `ansible/playbooks/switches/tasks/export-readonly-facts.yml`.
- Affected docs: `ansible/README.md`, `ansible/playbooks/switches/README.md`,
  and role READMEs if roles remain.
- Affected tests: `ansible/tests/test_xikeos_migration.py` should assert the
  chosen boundary: no repository-local platform/resource implementation, and any
  retained role only enforces repository policy.
