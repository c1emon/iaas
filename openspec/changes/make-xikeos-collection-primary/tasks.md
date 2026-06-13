## 1. Dependency and Documentation Baseline

- [ ] 1.1 Constrain `c1emon.xikeos` in `ansible/requirements.yml` to the v0.2.x baseline.
- [ ] 1.2 Update switch setup documentation to describe the v0.2.x baseline and required Python parser dependencies.
- [ ] 1.3 Document that `ansible_net_*` and `ansible_network_resources` replace the old `switch_facts` schema.

## 2. Read-Only Facts Workflow

- [ ] 2.1 Replace normal `switch_readonly_facts` collection internals with `c1emon.xikeos.xikeos_facts`.
- [ ] 2.2 Map role inputs to `xikeos_facts.gather_subset` and `gather_network_resources` values.
- [ ] 2.3 Remove normal workflow reliance on SKS8300 command plans, command IDs, stdout mapping, and local parser filters.
- [ ] 2.4 Expose collection-native facts to caller-owned playbook/export tasks.
- [ ] 2.5 Keep any `xikeos_command` usage limited to smoke, debug, or explicitly documented fallback workflows.

## 3. Facts Export Workflow

- [ ] 3.1 Rewrite switch facts export tasks to write collection-native `ansible_net_*` and `ansible_network_resources` data.
- [ ] 3.2 Remove normal export dependence on `switch_facts` and `switch_raw_export_items`.
- [ ] 3.3 Update export summary content to report collection module name, gather subsets, network resources, transport, and terminal adapter.
- [ ] 3.4 Ensure exported facts and reports do not expose plaintext secrets.

## 4. Configuration Lifecycle Workflow

- [ ] 4.1 Refactor current-state collection for configuration planning to use collection-native facts, gathered state, or resource module previews.
- [ ] 4.2 Extend declarative intent validation for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, and ACLs.
- [ ] 4.3 Map supported intent to lifecycle-complete `c1emon.xikeos` resource modules.
- [ ] 4.4 Preserve default plan-only behavior when `switch_config_apply` is not true.
- [ ] 4.5 Preserve apply gating, allowed-operation policy, destructive command blocking, redacted reporting, and post-apply verification.
- [ ] 4.6 Reject or clearly fail rendered-only resources that are not lifecycle-apply supported in v0.2.x.

## 5. Cleanup and Tests

- [ ] 5.1 Remove or isolate unused SKS8300 profile/parser/filter utilities after the collection-native paths no longer need them.
- [ ] 5.2 Update or remove tests that assert the old `switch_facts` schema, command IDs, or local parser behavior.
- [ ] 5.3 Add tests for `xikeos_facts` invocation, native fact export shape, and resource-module mapping.
- [ ] 5.4 Run relevant lint and unit tests for Ansible roles, filters, and OpenSpec artifacts.
- [ ] 5.5 Run safe switch smoke/check-mode playbooks when live device credentials are available.
