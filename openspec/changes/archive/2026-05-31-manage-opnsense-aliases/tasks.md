## 1. Desired State Input

- [x] 1.1 Add a hand-written OPNsense alias desired-state YAML file with a small reviewed starter set or documented empty structure.
- [x] 1.2 Ensure desired alias entries use fields compatible with `oxlorg.opnsense.alias_multi`, including name, type, content, description, enabled, and state where appropriate.

## 2. Alias Apply Workflow

- [x] 2.1 Add an OPNsense alias management playbook that loads the desired alias YAML source.
- [x] 2.2 Add preflight checks for required OPNsense API environment credentials before write operations.
- [x] 2.3 Apply aliases additively with `oxlorg.opnsense.alias_multi` without purge, delete, or disable behavior for unlisted aliases.
- [x] 2.4 Reload the OPNsense alias target once after successful alias create or update operations.

## 3. Documentation

- [x] 3.1 Document alias management usage, safety boundaries, and example command invocation in the OPNsense playbook README.
- [x] 3.2 Document that exported firewall aliases are observed live state and not the direct apply source for alias management.
- [x] 3.3 Document that alias type changes are not automatically migrated and require explicit operator handling.

## 4. Validation

- [x] 4.1 Add or document uv-managed Ansible syntax-check command for the alias management playbook.
- [x] 4.2 Run YAML/Ansible lint validation for the new YAML and playbook files.
- [x] 4.3 Verify no repository file contains real OPNsense API credentials.
