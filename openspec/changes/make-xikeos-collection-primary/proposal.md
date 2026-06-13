## Why

The project currently carries a repository-specific SKS8300 fact model and parser stack even though `c1emon.xikeos` v0.2.0 now provides native XikeOS facts and lifecycle resource modules. Because this repository is still test-only with no production consumers, we can reset the switch automation contract around the collection-native `ansible_net_*` and `ansible_network_resources` schemas instead of preserving compatibility with the old `switch_facts` shape.

## What Changes

- Require `c1emon.xikeos` v0.2.x as the switch collection baseline.
- **BREAKING**: Make `c1emon.xikeos.xikeos_facts` the primary read-only switch facts collector.
- **BREAKING**: Replace the repository-specific `switch_facts` schema with collection-native `ansible_net_*` facts and `ansible_network_resources` as the canonical switch state schema.
- **BREAKING**: Remove the requirement to preserve SKS8300 profile command planning, command IDs, local parsing, and raw command export contracts for normal facts collection.
- Expand configuration workflows to use lifecycle-complete `c1emon.xikeos` resource modules for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, and ACLs.
- Keep repository-level safety behaviors: explicit apply gate, destructive command blocking, auditable reports, and no arbitrary raw CLI command lists as the primary interface.
- Keep `xikeos_command` as a smoke/debug/fallback path only, not as the normal facts source.
- Exclude rendered-only modules such as STP, ERPS, EAPS, QinQ, mirror, port isolation, flex monitor link, and OSPF v2 from lifecycle apply support in this change.

## Capabilities

### New Capabilities

- `xikeos-network-resources-primary`: Collection-native XikeOS facts and resources become the canonical switch state model, centered on `ansible_network_resources`.

### Modified Capabilities

- `xikeos-collection-switch-automation`: Require the v0.2 collection baseline and treat collection-native facts/resource modules as the primary switch automation surface.
- `switch-cli-readonly-facts`: Replace parsed `switch_facts` output expectations with `xikeos_facts` and collection-native facts.
- `sks8300-profile-readonly-facts`: Remove compatibility-profile fact schema preservation as a normal requirement; local profile parsing becomes fallback/debug only if retained.
- `switch-readonly-facts-export-workflow`: Export collection-native facts instead of repository-specific `switch_facts` and command-ID raw outputs.
- `sks8300-config-resource-framework`: Extend declarative configuration coverage to lifecycle-complete collection resources and verify against `ansible_network_resources`.

## Impact

- Affected Ansible files: switch read-only facts role, switch configuration role, switch playbooks, switch export tasks, switch intent examples, and switch documentation.
- Affected local support code: SKS8300 profile/parser/filter utilities may be simplified, removed, or retained only for debug/fallback paths.
- Affected specs/tests: existing switch fact/export/config tests and OpenSpec requirements must be updated for the collection-native schema.
- Dependency impact: `ansible/requirements.yml` should constrain `c1emon.xikeos` to v0.2.x and documentation should continue to mention parser runtime dependencies such as `ttp` and `textfsm`.
