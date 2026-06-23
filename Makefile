ROOT ?= $(abspath .)
PVE_DIR ?= $(ROOT)/infra/tofu/pve
INVENTORY_DIR ?= $(ROOT)/inventory
UV ?= uv
TOFU ?= tofu
PACKER_BUILD_SCRIPT ?= $(ROOT)/infra/packer/proxmox/debian-13/build-template.sh

.PHONY: generate check-generated test lint-yaml tofu-fmt tofu-validate check pve-generate pve-check pve-validate pve-fmt pve-check-pve pve-packer-build pve-plan pve-apply pve-destroy pve-ansible-check pve-ansible-syntax pve-backup-state

generate:
	$(MAKE) -C "$(PVE_DIR)" generate

check-generated:
	$(MAKE) -C "$(PVE_DIR)" check-generated

test:
	$(UV) run --directory "$(ROOT)" pytest

lint-yaml:
	$(UV) run --directory "$(ROOT)" yamllint "$(INVENTORY_DIR)"

tofu-fmt:
	$(TOFU) -chdir="$(ROOT)/infra/tofu" fmt -recursive -check -diff

tofu-validate:
	$(TOFU) -chdir="$(PVE_DIR)" init -backend=false
	$(TOFU) -chdir="$(PVE_DIR)" validate

check: check-generated test lint-yaml tofu-fmt tofu-validate

pve-generate:
	$(MAKE) generate

pve-check:
	$(MAKE) check-generated

pve-validate:
	$(MAKE) -C "$(PVE_DIR)" validate

pve-fmt:
	$(MAKE) -C "$(PVE_DIR)" fmt

pve-check-pve:
	$(MAKE) -C "$(PVE_DIR)" check-pve

pve-packer-build:
	bash "$(PACKER_BUILD_SCRIPT)"

pve-plan:
	$(MAKE) -C "$(PVE_DIR)" plan

pve-apply:
	$(MAKE) -C "$(PVE_DIR)" apply

pve-destroy:
	$(MAKE) -C "$(PVE_DIR)" destroy

pve-ansible-check:
	$(MAKE) -C "$(PVE_DIR)" ansible-check

pve-ansible-syntax:
	$(MAKE) -C "$(PVE_DIR)" ansible-syntax

pve-backup-state:
	$(MAKE) -C "$(PVE_DIR)" backup-state
