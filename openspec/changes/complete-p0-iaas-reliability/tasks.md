## 1. State, Cache, and Secret Runbooks

- [ ] 1.1 Inventory existing state, cache, generated output, and environment template paths used by PVE automation.
- [ ] 1.2 Document local PVE OpenTofu state ownership, backup location, and when to run `make pve-backup-state`.
- [ ] 1.3 Document a local state restore procedure that does not perform automatic infrastructure mutation.
- [ ] 1.4 Document `.cache` contents, cleanup rules, and sensitivity expectations for state backups and rendered cloud-init snippets.
- [ ] 1.5 Document 1Password `op run --env-file ...` conventions for PVE OpenTofu, Packer/template build, VM cloud-init users, OPNsense, and switch workflows.
- [ ] 1.6 Document which generated outputs are committed and expected to remain non-sensitive.
- [ ] 1.7 Add an operator checklist for pre-operation and recovery steps around explicit plan/apply-like PVE workflows.

## 2. Secret Scanning and Hygiene Entry Points

- [ ] 2.1 Choose `gitleaks` or `trufflehog` for the first offline secret scanning implementation and document the rationale.
- [ ] 2.2 Add repository-owned scanner configuration, baseline, or allowlist if required to avoid known false positives.
- [ ] 2.3 Add root `make secret-scan` that runs without PVE, OPNsense, switch, SSH, 1Password, or apply-capable credentials.
- [ ] 2.4 Decide during implementation whether `secret-scan` is stable enough to become part of `make check`; if not, keep it explicit and have CI call it separately.
- [ ] 2.5 Update GitHub Actions to invoke repository-owned P0 hygiene targets without defining infrastructure secrets.
- [ ] 2.6 Ensure CI still does not run PVE preflight, OpenTofu plan/apply/destroy, Packer build, Ansible guest verification, or mutation workflows.

## 3. Explicit Ansible Syntax Validation

- [ ] 3.1 Inventory existing Ansible syntax-check targets and playbook assumptions.
- [ ] 3.2 Add or standardize an explicit root Ansible syntax validation target.
- [ ] 3.3 Keep Ansible syntax validation outside default `make check` for this P0 closure change.
- [ ] 3.4 Document the distinction between default offline checks and explicit Ansible syntax validation.

## 4. Passthrough Regression Coverage

- [ ] 4.1 Review existing passthrough tests for omitted, null, and empty passthrough declarations.
- [ ] 4.2 Add missing offline tests or assertions for omitted, null, and empty passthrough declarations producing no unintended host PCI inputs.
- [ ] 4.3 Add or verify tests for valid passthrough declarations preserving generated host PCI assignments and flags.
- [ ] 4.4 Add or verify tests for passthrough VM generated Ansible inventory behavior and cloud-init user-data expectations.
- [ ] 4.5 Add or verify tests for invalid passthrough mapping, duplicate override, invalid `hostpci` override, missing flags, and host PCI slot exhaustion errors.
- [ ] 4.6 Confirm passthrough regression tests require no live PVE PCI mapping access.

## 5. Documentation and Boundary Review

- [ ] 5.1 Update validation documentation to list default offline checks and optional explicit hygiene checks.
- [ ] 5.2 Update relevant PVE/Packer/Ansible docs to link to the state, cache, and secret operation guidance.
- [ ] 5.3 Confirm documented command names match actual root Makefile targets.
- [ ] 5.4 Confirm the implementation does not add online checks, plan, apply, destroy, Packer build, guest SSH verification, or internal CI triggers to default validation.

## 6. Validation

- [ ] 6.1 Run `make check` locally.
- [ ] 6.2 Run the new secret scanning command locally.
- [ ] 6.3 Run the explicit Ansible syntax validation target locally or document any blocker.
- [ ] 6.4 Run the passthrough-related test suite locally.
- [ ] 6.5 Run `openspec validate complete-p0-iaas-reliability`.
- [ ] 6.6 Inspect CI results after pushing the change.
