## 1. Role Structure Setup

- [x] 1.1 Create `ansible/roles/switch_readonly_facts/` with `defaults/`, `tasks/`, and role documentation files.
- [x] 1.2 Add `tasks/main.yml` as an explicit ordered import list for validation, preparation, collection, parsing, and export phases.
- [x] 1.3 Move workflow defaults such as command lists, mutation pattern, export formats, and export paths into `defaults/main.yml` where safe.
- [x] 1.4 Keep SSH/network connection variables in inventory/group vars rather than hard-coding them in the role.

## 2. Task Phase Extraction

- [x] 2.1 Move credential, adapter, export format, and read-only command assertions into `tasks/validate.yml` without weakening guardrails.
- [x] 2.2 Move export directory creation into `tasks/prepare.yml` while preserving modes and raw-output conditional behavior.
- [x] 2.3 Move `ansible.netcommon.cli_command` collection and raw stdout selection into `tasks/collect.yml` without changing registered fact semantics needed downstream.
- [x] 2.4 Move output normalization, named command output facts, structured facts building, and running-config redaction into `tasks/parse.yml`.
- [x] 2.5 Move YAML/JSON export, raw-output summary, redacted running-config export, non-sensitive raw command exports, generated README, and final debug message into `tasks/export.yml`.

## 3. Playbook and Documentation Update

- [x] 3.1 Replace `readonly-facts.yml` task body with invocation of the `switch_readonly_facts` role while preserving play target, `gather_facts`, and `network_cli` connection behavior.
- [x] 3.2 Update switch playbook documentation to describe the role-based layout and unchanged operator commands.
- [x] 3.3 Update validation command examples to include role files where relevant for linting and syntax checks.
- [x] 3.4 Ensure `network-cli-smoke.yml` remains a separate manual validation utility and is not coupled to the role refactor.

## 4. Behavior Preservation Validation

- [x] 4.1 Run syntax checks for `readonly-facts.yml` with the role in place.
- [x] 4.2 Run `yamllint` on the changed playbook, inventory variables, and role YAML files.
- [x] 4.3 Run `ansible-lint` on `readonly-facts.yml` and address any role-related lint issues without changing behavior.
- [x] 4.4 Run the role-backed read-only facts playbook against `sw-core` with SSH credentials and raw export enabled. Skipped by operator risk acceptance after 1Password authorization timeout; live validation is superseded by `profile-driven-sks8300-readonly-facts`.
- [x] 4.5 Verify generated YAML and JSON exports still include expected device version facts, VLAN facts, and interface membership facts. Skipped by operator risk acceptance; to be covered by the follow-up profile-driven change.
- [x] 4.6 Verify raw-output export still writes `cli-output-summary.json`, non-sensitive raw command files, and redacted `show-running-config.txt` without plaintext management secrets. Skipped by operator risk acceptance; to be covered by the follow-up profile-driven change.
