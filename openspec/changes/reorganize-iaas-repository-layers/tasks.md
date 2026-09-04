## 1. Contract and baseline

- [ ] 1.1 Confirm the target layout, path map, hard cutover, and non-goals.
- [ ] 1.2 Run the required GitNexus impact/context checks before implementation and resolve reported risk according to repository rules.
- [ ] 1.3 Run the existing offline gate and record pre-existing failures.

## 2. Restore PVE and VM inventory authority

- [ ] 2.1 Remove concrete Astra PVE/VM values from reusable validators where they duplicate inventory declarations.
- [ ] 2.2 Preserve structural, relationship, network, provider-limit, lifecycle, and secret-safety validation; update focused positive and negative tests.
- [ ] 2.3 Run focused inventory, renderer, health-expectation, preflight-expectation, and secret-redaction tests.

## 3. Move Python code and tests

- [ ] 3.1 Move the actual Python packages under `scripts/` to `automation/src/iaas_automation/` and update packaging configuration; merge `scripts/README.md` into current automation documentation.
- [ ] 3.2 Update supported imports and commands to `iaas_automation.*`; delete `scripts/validate_pve_inventory.py` and retain no package compatibility route.
- [ ] 3.3 Add the required explicit source/output CLI arguments, move tests under `tests/`, and run focused tests and type checks.

## 4. Move the Astra environment

- [ ] 4.1 Move PVE, VM, service, and foundation inventories to `environments/astra/inventory/`.
- [ ] 4.2 Move Astra Ansible data to `environments/astra/ansible/` and runtime-reference templates to `environments/astra/runtime/` without renaming external variables or secret references.
- [ ] 4.3 Discard `terraform.tfstate*` in the old OpenTofu root without copying it, leave ignored backup caches untouched, then move generated outputs and the Astra OpenTofu root to their new paths.
- [ ] 4.4 Update all producers, consumers, and the root Makefile for the new source, generated-output, Ansible, Packer, and OpenTofu paths.
- [ ] 4.5 Run inventory, generation/check, OpenTofu offline, and Ansible inventory checks.

## 5. Move reusable automation

- [ ] 5.1 Move reusable Ansible configuration, requirements, playbooks, roles, and utilities to `automation/ansible/`.
- [ ] 5.2 Move reusable OpenTofu modules to `automation/opentofu/modules/` and update module sources.
- [ ] 5.3 Move Packer and PVE-node automation under `automation/`, preserving their existing external interfaces.
- [ ] 5.4 Run focused Ansible, OpenTofu, Packer, wrapper, sudoers-path, and executable-mode checks.

## 6. Complete the cutover

- [ ] 6.1 Leave existing ignored backup, cache, export, and observation layouts unchanged except for necessary consumer path updates.
- [ ] 6.2 Update CI, ignore rules, validation paths, and the single Ansible configuration.
- [ ] 6.3 Remove old supported paths and compatibility routes for moved paths or `scripts.*`; remove the confirmed orphaned `terraform/README.md` and `pnpm-workspace.yaml` only.
- [ ] 6.4 Update current documentation and this change's delta specs, merge relocated module documentation, and add the design-only `platform/README.md`; leave historical archives unchanged.

## 7. Final verification

- [ ] 7.1 Verify current code, CI, tests, documentation, and this change's delta specs use the new paths and package name only.
- [ ] 7.2 Run the complete existing offline gate and secret scan, then review generated diffs for unexpected semantic changes.
- [ ] 7.3 Strictly validate this change and report unrelated full-repository OpenSpec failures separately.
- [ ] 7.4 Run the required complete GitNexus change analysis before commits, review the final worktree, and confirm no live infrastructure or K3s work was introduced.
