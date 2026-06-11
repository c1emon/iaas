## Context

The repository currently manages the SKS8300/Xike switch through SSH `network_cli` while declaring `ansible_network_os: cisco.ios.ios`. That Cisco setting is used as a terminal compatibility adapter, not as a true device platform model. The repository then supplies local SKS8300 profile code for read-only command planning, parsing, redaction, and a custom declarative VLAN/interface configuration workflow.

The `c1emon.xikeos` collection in `~/Workplace/xike-xikeos` provides the missing native XikeOS collection layer: `plugins/cliconf/xikeos.py`, `plugins/terminal/xikeos.py`, `xikeos_command`, `xikeos_config`, and lifecycle-oriented resource modules such as `xikeos_vlans`, `xikeos_interfaces`, `xikeos_l2_interfaces`, `xikeos_l3_interfaces`, and `xikeos_lag_interfaces`. Its documented inventory uses `ansible_network_os: c1emon.xikeos.xikeos` with `ansible.netcommon.network_cli`.

This change should adopt that native collection without losing the repository's existing safety properties: read-only facts must remain non-mutating, configuration must remain declarative, apply must remain explicit, destructive commands must remain blocked, and reports must remain auditable and redacted.

## Goals / Non-Goals

**Goals:**
- Use `c1emon.xikeos` as the native switch automation collection dependency.
- Replace the Cisco IOS network OS adapter with `c1emon.xikeos.xikeos` for switch inventory.
- Prefer collection modules for XikeOS command execution and VLAN/interface resource mutation where they provide equivalent or better semantics.
- Preserve repository-level controls around planning, explicit apply, allowed operations, verification, export/report ownership, and redaction.
- Keep migration incremental so existing read-only and configuration workflows can be validated independently.

**Non-Goals:**
- Do not redesign OPNsense automation.
- Do not replace safe declarative resource workflows with arbitrary raw configuration lines.
- Do not require full removal of all local SKS8300 parser/profile code in the first implementation if collection-backed output does not yet cover an equivalent fact schema.
- Do not make `c1emon.xikeos.xikeos_config` the default configuration interface.
- Do not publish or modify the `c1emon.xikeos` collection as part of this repository change.

## Decisions

### Use `c1emon.xikeos.xikeos` as the platform adapter

The switch inventory should declare `ansible_network_os: c1emon.xikeos.xikeos` and keep `ansible_connection: ansible.netcommon.network_cli`.

Rationale: the collection provides native `cliconf` and `terminal` plugins for XikeOS, avoiding the conceptual mismatch of using `cisco.ios.ios` as a transport shim.

Alternative considered: keep `cisco.ios.ios` and only add collection modules. Rejected because collection modules expect their own `cliconf` behavior and the repository would continue documenting an inaccurate platform.

### Add the collection through repository requirements

The collection dependency should be added to `ansible/requirements.yml`, and docs should continue to direct operators to install repository requirements with `uv run ansible-galaxy collection install -r ansible/requirements.yml`.

Rationale: this keeps setup reproducible for all Ansible dependencies rather than relying on an out-of-band one-off install command.

Alternative considered: document only `ansible-galaxy collection install c1emon.xikeos`. Rejected as the primary path because it bypasses the repository dependency manifest, though it can be mentioned as the underlying Galaxy command.

### Preserve repository orchestration around collection resource modules

The repository should call `c1emon.xikeos` resource modules from playbooks/roles, but retain repository-level policy and report semantics where the current workflow is stricter than a direct module invocation.

Rationale: `xikeos_vlans` and related modules provide facts-backed lifecycle behavior with check mode, commands, before, and after results, but the repository still owns `switch_config_apply`, `switch_config_allowed_operations`, exported change reports, and verification expectations.

Alternative considered: delete `switch_config` and have operators call collection resource modules directly. Rejected for this change because it would remove existing safety and audit conventions from repository workflows.

### Treat raw config as fallback only

`c1emon.xikeos.xikeos_config` should not become the primary declarative interface. It may be used only for documented fallback gaps when no lifecycle-safe resource module exists and when repository guardrails still validate the operation.

Rationale: `xikeos_config` supports check mode but explicitly does not support diff or backup and applies raw lines. Using it broadly would reintroduce the arbitrary command-list risk the current design intentionally avoids.

Alternative considered: replace local rendered command application with `xikeos_config` everywhere. Rejected because it weakens idempotency, diff, and safety semantics.

### Keep read-only exports caller-owned

The read-only facts workflow should continue to produce structured facts and export-plan data without writing files inside the role. Collection-backed command or gathered-resource output can feed that workflow, but export location, format, and raw-save controls remain outside the role.

Rationale: this preserves the previously established separation between fact collection and persistence side effects.

Alternative considered: use collection module output directly from ad hoc playbooks and bypass the role/export workflow. Rejected as the default because it would fragment the repository fact schema and export behavior.

## Risks / Trade-offs

- Collection parser dependencies missing (`ttp`, `textfsm`) → Document Python runtime dependencies and validate the Ansible control environment before collection-backed facts/resources are used.
- Collection fact schema differs from current `switch_facts` schema → Add an adaptation layer or retain local parsers until equivalent structured output is confirmed.
- Resource module behavior differs on SKS8300 firmware `V300SP10240912` → Start with check-mode/rendered/gathered validation and a limited VLAN/interface migration before broader replacement.
- `xikeos_config` could be overused as a shortcut → Keep spec language and tasks explicit that raw config is fallback-only and not the primary interface.
- `c1emon.xikeos` version `0.1.0` may change quickly → Pin or document version expectations when implementation selects dependency syntax.
- Native `cliconf` still uses `configure terminal` internally → Validate against the target switch; this is acceptable only if it matches XikeOS behavior and is no longer inherited from Cisco IOS plugin assumptions.

## Migration Plan

1. Add `c1emon.xikeos` to collection requirements and document collection/Python dependency installation.
2. Change switch inventory network OS to `c1emon.xikeos.xikeos` while retaining `ansible.netcommon.network_cli` and SSH credential variables.
3. Validate connectivity with a non-mutating command path such as `xikeos_command` for `show version` and existing read-only playbook expectations.
4. Migrate read-only collection internals where collection modules provide equivalent command/gather behavior, preserving `switch_facts` outputs and caller-owned exports.
5. Migrate VLAN/interface configuration execution to lifecycle-safe `c1emon.xikeos` resource modules behind the existing apply gate and reporting workflow.
6. Keep local SKS8300 profile code only where still needed for schema adaptation, redaction, or verification gaps; remove or simplify it only after equivalent behavior is proven.

Rollback is to remove the collection dependency usage, restore `ansible_network_os: cisco.ios.ios`, and continue using the existing local SKS8300 profile workflows. Runtime rollback for applied network configuration remains manual or plan-based unless a resource module provides a safe inverse operation.

## Open Questions

- Should the initial dependency specify an exact `c1emon.xikeos` version or allow the latest Galaxy release?
- Which current `switch_facts` fields can be populated directly from collection gathered output, and which still require local parser compatibility code?
- Should `switch_config` remain a long-term orchestration role, or become a thin compatibility wrapper around collection modules after migration stabilizes?
- What live-device smoke tests are acceptable before using collection resource modules against `sw-core`?
