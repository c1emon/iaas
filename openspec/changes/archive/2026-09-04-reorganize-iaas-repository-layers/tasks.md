## 1. Contract and baseline

- [x] 1.1 Confirm the target layout, path map, hard cutover, and non-goals.
- [x] 1.2 Run the required GitNexus impact/context checks before implementation and resolve reported risk according to repository rules.
- [x] 1.3 Run the existing offline gate and record pre-existing failures.

## 2. Restore PVE and VM inventory authority

- [x] 2.1 Remove concrete Astra PVE/VM values from reusable validators where they duplicate inventory declarations.
- [x] 2.2 Preserve structural, relationship, network, provider-limit, lifecycle, and secret-safety validation; update focused positive and negative tests.
- [x] 2.3 Run focused inventory, renderer, health-expectation, preflight-expectation, and secret-redaction tests.

## 3. Move Python code and tests

- [x] 3.1 Move the actual Python packages under `scripts/` to `automation/src/iaas_automation/` and update packaging configuration; merge `scripts/README.md` into current automation documentation.
- [x] 3.2 Update supported imports and commands to `iaas_automation.*`; delete `scripts/validate_pve_inventory.py` and retain no package compatibility route.
- [x] 3.3 Add the required explicit source/output CLI arguments, move tests under `tests/`, and run focused tests and type checks.

## 4. Move the Astra environment

- [x] 4.1 Move PVE, VM, service, and foundation inventories to `environments/astra/inventory/`.
- [x] 4.2 Move Astra Ansible data to `environments/astra/ansible/` and runtime-reference templates to `environments/astra/runtime/` without renaming external variables or secret references.
- [x] 4.3 Discard `terraform.tfstate*` in the old OpenTofu root without copying it, leave ignored backup caches untouched, then move generated outputs and the Astra OpenTofu root to their new paths.
- [x] 4.4 Update all producers, consumers, and the root Makefile for the new source, generated-output, Ansible, Packer, and OpenTofu paths.
- [x] 4.5 Run inventory, generation/check, OpenTofu offline, and Ansible inventory checks.

## 5. Move reusable automation

- [x] 5.1 Move reusable Ansible configuration, requirements, playbooks, roles, and utilities to `automation/ansible/`.
- [x] 5.2 Move reusable OpenTofu modules to `automation/opentofu/modules/` and update module sources.
- [x] 5.3 Move Packer and PVE-node automation under `automation/`; require the generated Packer environment file explicitly through `TEMPLATE_BUILD_ENV` without a sibling-file fallback.
- [x] 5.4 Run focused Ansible, OpenTofu, Packer, wrapper, sudoers-path, and executable-mode checks.

## 6. Complete the cutover

- [x] 6.1 Leave existing ignored backup, cache, export, and observation layouts unchanged except for necessary consumer path updates.
- [x] 6.2 Update CI, ignore rules, validation paths, and the single Ansible configuration.
- [x] 6.3 Remove old supported paths and compatibility routes for moved paths or `scripts.*`; remove the confirmed orphaned `terraform/README.md` and `pnpm-workspace.yaml` only.
- [x] 6.4 Update current documentation and this change's delta specs, merge relocated module documentation, and add the design-only `platform/README.md`; leave historical archives unchanged.

## 7. Final verification

- [x] 7.1 Verify current code, CI, tests, documentation, and this change's delta specs use the new paths and package name only.
- [x] 7.2 Run the complete existing offline gate and secret scan, then review generated diffs for unexpected semantic changes.
- [x] 7.3 Strictly validate this change and report unrelated full-repository OpenSpec failures separately.
- [x] 7.4 Run the required complete GitNexus change analysis before commits, review the final worktree, and confirm no live infrastructure or K3s work was introduced.
