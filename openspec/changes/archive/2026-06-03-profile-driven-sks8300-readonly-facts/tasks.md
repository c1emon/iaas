## 1. Profile Core Structure

- [x] 1.1 Create `ansible/module_utils/switch_profiles/` with registry, read orchestration, shared errors, and common helpers.
- [x] 1.2 Create `ansible/module_utils/switch_profiles/sks8300/` with profile, command catalog, read subset registry, parser, and redaction modules.
- [x] 1.3 Move existing SKS8300 parsing and running-config redaction logic out of `filter_plugins/switch_cli_facts.py` into the SKS8300 profile core without changing parsed facts schema.
- [x] 1.4 Implement `sks8300` profile lookup and validation so unsupported profiles fail with clear errors before collection.

## 2. Gather Subset and Command Planning

- [x] 2.1 Add role defaults for `switch_platform_profile: sks8300` and `switch_readonly_gather_subset`, and remove user-facing command-list defaults such as `switch_cli_commands`.
- [x] 2.2 Define SKS8300 gather subsets for current behavior, including `default`, `device`, `vlans`, and `interfaces`.
- [x] 2.3 Implement command planning from gather subsets with deduplication, stable command IDs, required setup ordering, read-only flags, sensitivity flags, and raw export policy.
- [x] 2.4 Validate that command planning rejects unsupported subsets and any non-read-only or mutating command definitions.

## 3. Filter Facade and Role Integration

- [x] 3.1 Add `ansible/filter_plugins/switch_profiles.py` as a thin Ansible-facing facade for command planning, output mapping, fact parsing, and raw export planning.
- [x] 3.2 Add `tasks/plan.yml` to `switch_readonly_facts` and import it between validation/preparation and collection.
- [x] 3.3 Update `tasks/collect.yml` to run `ansible.netcommon.cli_command` over the profile-generated command plan rather than `switch_cli_commands`.
- [x] 3.4 Update `tasks/parse.yml` to map CLI results by command ID and parse selected gather subsets through the profile facade.
- [x] 3.5 Update `tasks/export.yml` to write raw outputs according to command-level export policy while preserving YAML/JSON structured exports.
- [x] 3.6 Keep SSH/network connection variables in inventory/group vars and keep the playbook entrypoint role-based.

## 4. Documentation and Migration Notes

- [x] 4.1 Update switch playbook documentation to describe `switch_platform_profile` and `switch_readonly_gather_subset` as the supported user interface.
- [x] 4.2 Remove documentation examples that tell operators to override `switch_cli_commands` or other command-list variables.
- [x] 4.3 Document the MikroTik-inspired separation between gather subsets, command catalog, profile core, and future configuration resources.
- [x] 4.4 Update validation command examples to include new `filter_plugins/` and `module_utils/` files where relevant.

## 5. Static Validation

- [x] 5.1 Run syntax checks for `playbooks/switches/readonly-facts.yml` with the profile-driven role in place.
- [x] 5.2 Run `yamllint` on changed playbook, inventory variables, role YAML files, and any new YAML files.
- [x] 5.3 Run `ansible-lint` on `playbooks/switches/readonly-facts.yml` and `roles/switch_readonly_facts` and address profile-related issues without changing behavior.
- [x] 5.4 Run available Python validation or unit-style checks for the moved parser/profile code if a project test harness exists.

## 6. Live Behavior Validation

- [x] 6.1 Run the role-backed read-only facts playbook against `sw-core` with SSH credentials and raw export enabled.
- [x] 6.2 Verify generated YAML and JSON exports still include expected device version facts, VLAN facts, and interface membership facts.
- [x] 6.3 Verify raw-output export writes command summary, non-sensitive raw command files, and redacted `show-running-config.txt` without plaintext management secrets.
- [x] 6.4 Verify unsupported profile or gather subset values fail before connecting or collecting commands.
