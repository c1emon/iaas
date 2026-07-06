## 1. Ansible role and defaults

- [x] 1.1 Create `ansible/roles/vm_baseline/` with defaults for baseline packages, services, hostname behavior, reboot reporting, and network-validation mode.
- [x] 1.2 Implement baseline package installation with `ansible.builtin.apt`, using `state: present` and avoiding broad package upgrades by default.
- [x] 1.3 Implement baseline service management for qemu-guest-agent and time synchronization with idempotent Ansible modules.
- [x] 1.4 Implement hostname convergence or validation against generated inventory identity while keeping VM-specific data out of templates.
- [x] 1.5 Implement reboot-required detection and reporting without automatically rebooting guests.
- [x] 1.6 Add read-only guest network fact checks that report expected IP/gateway/DNS facts without editing network configuration.

## 2. Bootstrap playbook and entrypoints

- [x] 2.1 Add `ansible/playbooks/pve/bootstrap-guests.yml` targeting the generated `pve_vms` group and applying the `vm_baseline` role.
- [x] 2.2 Ensure the playbook uses generated SSH metadata and privilege escalation safely through the existing `ops` user flow.
- [x] 2.3 Support operator narrowing through standard Ansible limit behavior without adding a separate bootstrap inventory.
- [x] 2.4 Add PVE Makefile targets for guest bootstrap and bootstrap syntax check.
- [x] 2.5 Add root Makefile targets that delegate to the PVE guest bootstrap and syntax-check targets.
- [x] 2.6 Keep existing `pve-verify-guests` read-only and separate from the bootstrap workflow.

## 3. Documentation

- [x] 3.1 Document the cloud-init → Ansible VM bootstrap → guest verification flow in the PVE or operator documentation.
- [x] 3.2 Document bootstrap safety boundaries, including no PVE lifecycle mutation and no guest network mutation in the first version.
- [x] 3.3 Document how ordinary VMs and future K3s nodes reuse the common VM bootstrap role.
- [x] 3.4 Document example commands for syntax check, limited bootstrap, full bootstrap, and follow-up verification.

## 4. Validation

- [x] 4.1 Run `uv run --directory . ansible-playbook --syntax-check -i ansible/inventories/generated/pve.yml ansible/playbooks/pve/bootstrap-guests.yml`.
- [x] 4.2 Run `uv run --directory . ansible-lint ansible/playbooks/pve/bootstrap-guests.yml` or document any unavailable lint dependency.
- [x] 4.3 Run `uv run --directory . yamllint ansible/playbooks/pve/bootstrap-guests.yml ansible/roles/vm_baseline`.
- [x] 4.4 Run existing PVE guest verification syntax checks and ensure the read-only verification workflow still passes syntax validation.
- [x] 4.5 Run relevant repository tests with `uv run --directory . pytest`.
- [x] 4.6 Run `openspec status --change support-vm-ansible-bootstrap` and confirm the change is apply-ready.
