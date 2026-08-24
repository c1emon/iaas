ROOT ?= $(abspath .)
PVE_DIR ?= $(ROOT)/infra/tofu/pve
INVENTORY_DIR ?= $(ROOT)/inventory
UV ?= uv
TOFU ?= tofu
GITLEAKS ?= gitleaks
ANSIBLE_LINT_PATHS ?= $(ROOT)/ansible/playbooks/pve $(ROOT)/ansible/playbooks/opnsense $(ROOT)/ansible/roles/vm_baseline
PACKER_BUILD_SCRIPT ?= $(ROOT)/infra/packer/proxmox/debian-13/build-template.sh

.PHONY: generate check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate check secret-scan ansible-syntax pve-generate pve-check services-generate services-check foundation-generate foundation-check foundation-health pve-validate pve-fmt pve-preflight pve-health pve-check-pve pve-packer-build pve-plan pve-apply pve-destroy pve-verify-guests pve-bootstrap-guests pve-bootstrap-guests-syntax pve-ansible-check pve-ansible-syntax pve-backup-state

generate:
	$(MAKE) -C "$(PVE_DIR)" generate
	$(MAKE) services-generate
	$(MAKE) foundation-generate

check-generated:
	$(MAKE) -C "$(PVE_DIR)" check-generated
	$(MAKE) services-check
	$(MAKE) foundation-check

test:
	$(UV) run --directory "$(ROOT)" pytest

lint-yaml:
	$(UV) run --directory "$(ROOT)" yamllint "$(INVENTORY_DIR)"

typecheck:
	$(UV) run --directory "$(ROOT)" pyright

ansible-lint:
	$(UV) run --directory "$(ROOT)" ansible-lint $(ANSIBLE_LINT_PATHS)

tofu-fmt:
	$(TOFU) -chdir="$(ROOT)/infra/tofu" fmt -recursive -check -diff

tofu-validate:
	$(TOFU) -chdir="$(PVE_DIR)" init -backend=false
	$(TOFU) -chdir="$(PVE_DIR)" validate

opnsense-validate:
	$(UV) run --directory "$(ROOT)" python -m scripts.opnsense_validation

check: check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate

secret-scan:
	@command -v "$(GITLEAKS)" >/dev/null 2>&1 || { printf 'error: gitleaks is required for secret-scan (install gitleaks or set GITLEAKS=/path/to/gitleaks)\n' >&2; exit 127; }
	$(GITLEAKS) detect --source "$(ROOT)" --config "$(ROOT)/.gitleaks.toml" --no-banner --redact

ansible-syntax: pve-ansible-syntax

pve-generate:
	$(MAKE) -C "$(PVE_DIR)" generate

pve-check:
	$(MAKE) -C "$(PVE_DIR)" check-generated

services-generate:
	$(UV) run --directory "$(ROOT)" python -m scripts.services_inventory.cli --generate

services-check:
	$(UV) run --directory "$(ROOT)" python -m scripts.services_inventory.cli --check

foundation-generate:
	$(UV) run --directory "$(ROOT)" python -m scripts.foundation_inventory.cli --generate

foundation-check:
	$(UV) run --directory "$(ROOT)" python -m scripts.foundation_inventory.cli --check

foundation-health:
	$(UV) run --directory "$(ROOT)" python -m scripts.foundation_inventory.cli --health

pve-validate:
	$(MAKE) -C "$(PVE_DIR)" validate

pve-fmt:
	$(MAKE) -C "$(PVE_DIR)" fmt

pve-preflight:
	$(MAKE) -C "$(PVE_DIR)" pve-preflight

pve-health:
	$(MAKE) -C "$(PVE_DIR)" pve-health

pve-check-pve:
	$(MAKE) -C "$(PVE_DIR)" pve-preflight

pve-packer-build:
	bash "$(PACKER_BUILD_SCRIPT)"

pve-plan:
	$(MAKE) -C "$(PVE_DIR)" plan

pve-apply:
	$(MAKE) -C "$(PVE_DIR)" apply

pve-destroy:
	$(MAKE) -C "$(PVE_DIR)" destroy

pve-verify-guests:
	$(MAKE) -C "$(PVE_DIR)" verify-guests

pve-bootstrap-guests:
	$(MAKE) -C "$(PVE_DIR)" bootstrap-guests

pve-bootstrap-guests-syntax:
	$(MAKE) -C "$(PVE_DIR)" bootstrap-guests-syntax

pve-ansible-check:
	$(MAKE) pve-verify-guests

pve-ansible-syntax:
	$(MAKE) -C "$(PVE_DIR)" ansible-syntax

pve-backup-state:
	$(MAKE) -C "$(PVE_DIR)" backup-state
