TOFU ?= tofu
UV ?= uv
ROOT ?= $(abspath ../../../)
STATE_FILE ?= terraform.tfstate
BACKUP_DIR ?= $(ROOT)/.cache/tofu-state-backups
USER_DATA_DIR ?= $(ROOT)/.cache/pve-cloud-init/user-data
ANSIBLE_INVENTORY ?= $(ROOT)/ansible/inventories/generated/pve.yml
ANSIBLE_PLAYBOOK ?= $(ROOT)/ansible/playbooks/pve/verify-guests.yml
ANSIBLE_LIMIT ?= pve_vms
PACKER_BUILD_SCRIPT ?= $(ROOT)/infra/packer/proxmox/debian-13/build-template.sh

.PHONY: backup-state generate check-generated validate-source validate-ansible validate fmt init pve-preflight pve-health check-pve render-user-data upload-user-data verify-user-data verify-guests verify-guests-syntax plan apply destroy tofu-plan tofu-apply tofu-destroy packer-build ansible-check ansible-syntax

backup-state:
	@mkdir -p "$(BACKUP_DIR)"
	@stamp="$$(date +%Y%m%dT%H%M%S)_$$$$"; phase="$${BACKUP_PHASE:-snapshot}"; if [ -f "$(STATE_FILE)" ]; then cp "$(STATE_FILE)" "$(BACKUP_DIR)/$${stamp}-$${phase}-$(STATE_FILE)"; fi

generate:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cli --generate

check-generated:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cli --check

validate-source:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cli

validate-ansible:
	$(UV) run --directory "$(ROOT)" ansible-inventory -i "$(ANSIBLE_INVENTORY)" --list >/dev/null

validate: validate-source validate-ansible check-generated init
	$(TOFU) validate

fmt:
	$(TOFU) fmt -recursive

init:
	$(TOFU) init -backend=false

pve-preflight:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.preflight

pve-health:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.health

check-pve: pve-preflight

require-storage-id:
	@test -n "$(STORAGE_ID)" || { printf 'error: STORAGE_ID is required\n' >&2; exit 1; }

require-pve-target: require-storage-id
	@test -n "$(PVE_HOST)" || { printf 'error: PVE_HOST is required\n' >&2; exit 1; }
	@test -n "$(PVE_SSH_USER)" || { printf 'error: PVE_SSH_USER is required\n' >&2; exit 1; }

render-user-data: require-storage-id
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init render --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)"

upload-user-data: require-pve-target
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init upload --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

verify-user-data: require-pve-target
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init verify --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

verify-guests:
	$(UV) run --directory "$(ROOT)" ansible-playbook -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"

verify-guests-syntax:
	$(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"

ansible-check: verify-guests

ansible-syntax: verify-guests-syntax

packer-build:
	bash "$(PACKER_BUILD_SCRIPT)"

plan: render-user-data
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) plan

apply:
	$(MAKE) render-user-data
	$(MAKE) upload-user-data verify-user-data
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) apply
	$(MAKE) backup-state BACKUP_PHASE=after

destroy:
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) destroy
	$(MAKE) backup-state BACKUP_PHASE=after

tofu-plan: plan

tofu-apply: apply

tofu-destroy: destroy
