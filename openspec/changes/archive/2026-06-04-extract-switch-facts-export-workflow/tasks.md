## 1. Role Boundary Cleanup

- [x] 1.1 Remove `export.yml` from `roles/switch_readonly_facts/tasks/main.yml` so the role ends after parsing.
- [x] 1.2 Remove export path, format, raw-save, and raw-output directory defaults from `roles/switch_readonly_facts/defaults/main.yml`.
- [x] 1.3 Ensure `switch_readonly_facts` still exposes `switch_facts`, `switch_command_outputs`, `switch_raw_export_items`, `switch_read_command_plan`, and CLI result variables after parsing.
- [x] 1.4 Confirm the role can run without export variables being defined by the role defaults.

## 2. Playbook-Level Export Workflow

- [x] 2.1 Create a playbook-level export task file, such as `playbooks/switches/tasks/export-readonly-facts.yml`, from the existing role export behavior.
- [x] 2.2 Move structured YAML/JSON export writing to the playbook-level export task file using `switch_facts`.
- [x] 2.3 Move raw output summary writing to the playbook-level export task file using role output variables.
- [x] 2.4 Move raw command file writing to the playbook-level export task file using `switch_raw_export_items`.
- [x] 2.5 Preserve `facts.yml`, `facts.json`, `raw-output/cli-output-summary.json`, raw command filenames, and `README.md` output layout for the switch playbook.

## 3. Playbook Variables and Entrypoint

- [x] 3.1 Define export variables at `playbooks/switches/readonly-facts.yml` or playbook-local scope rather than role defaults.
- [x] 3.2 Import the playbook-level export workflow after `switch_readonly_facts` in `playbooks/switches/readonly-facts.yml`.
- [x] 3.3 Preserve current playbook behavior for operators who run the switch read-only facts playbook with raw export disabled by default.
- [x] 3.4 Preserve raw export behavior when `switch_export_save_raw=true` is supplied by the operator.

## 4. Documentation Updates

- [x] 4.1 Update `roles/switch_readonly_facts/README.md` to describe the role as a side-effect-free facts provider and list its output variables.
- [x] 4.2 Update `playbooks/switches/README.md` to describe file export as a playbook-level workflow, not role-internal behavior.
- [x] 4.3 Document the migration for callers that previously expected `switch_readonly_facts` to write files.
- [x] 4.4 Update validation command examples if task file paths change.

## 5. Static Validation

- [x] 5.1 Run syntax check for `playbooks/switches/readonly-facts.yml` after moving export tasks.
- [x] 5.2 Run `yamllint` on changed playbook, playbook task files, role YAML files, and inventory variable files.
- [x] 5.3 Run `ansible-lint` on `playbooks/switches/readonly-facts.yml` and `roles/switch_readonly_facts`.
- [x] 5.4 Run available Python validation or compile checks for unchanged profile/filter code if touched during the refactor.

## 6. Behavior Validation

- [x] 6.1 Run the role-backed switch read-only facts playbook against `sw-core` with default export settings.
- [x] 6.2 Run the switch read-only facts playbook against `sw-core` with `switch_export_save_raw=true`.
- [x] 6.3 Verify generated YAML/JSON exports still include expected device, VLAN, and interface facts when the playbook export workflow runs.
- [x] 6.4 Verify raw-output export still writes the command summary, non-sensitive raw command files, and redacted `show-running-config.txt` without plaintext management secrets.
- [x] 6.5 Verify the `switch_readonly_facts` role can be used without invoking the export task file and does not create export directories or files by itself.
