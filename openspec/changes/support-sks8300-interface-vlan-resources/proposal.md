## Why

The SKS8300 configuration framework currently manages VLAN definitions but cannot declaratively manage switchport VLAN membership. Operators need a safe way to plan, apply, and verify interface mode plus tagged/untagged/access VLAN settings without falling back to raw CLI commands.

## What Changes

- Extend the SKS8300 declarative configuration workflow with an `interfaces` resource.
- Allow operators to declare interface switchport mode and VLAN membership intent for access, trunk, and hybrid-style ports.
- Reuse existing SKS8300 read-only interface parsing for current-state collection and post-apply verification.
- Render SKS8300 interface configuration commands from validated resource diffs rather than operator-provided command strings.
- Keep `switch_config_apply: false` as the default and require explicit apply for live port changes.
- Update host-specific switch VLAN vars documentation/examples to include optional interface intent.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sks8300-config-resource-framework`: Add SKS8300 interface VLAN resource intent for port mode, access VLAN, tagged VLAN IDs, and untagged VLAN IDs.

## Impact

- Shared Python profile core:
  - `ansible/module_utils/switch_profiles/sks8300/resources.py`
  - `ansible/module_utils/switch_profiles/sks8300/parsers.py` if parser normalization needs adjustment
- Ansible role/playbook configuration:
  - `ansible/roles/switch_config/`
  - `ansible/playbooks/switches/config-plan.yml`
  - `ansible/vars/switches/<inventory_hostname>-vlans.yml`
- OpenSpec capability:
  - `openspec/specs/sks8300-config-resource-framework/spec.md`
- Live validation requires operator approval and a low-risk unused switch port because interface VLAN changes can disrupt connectivity.
