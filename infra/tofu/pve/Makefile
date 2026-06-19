TOFU ?= tofu
UV ?= uv
ROOT ?= $(abspath ../../../)
STATE_FILE ?= terraform.tfstate
BACKUP_DIR ?= $(ROOT)/.cache/tofu-state-backups
USER_DATA_DIR ?= $(ROOT)/.cache/pve-cloud-init/user-data
STORAGE_ID ?= images
PVE_HOST ?= cohe
PVE_SSH_USER ?= pve-ops

.PHONY: backup-state init fmt validate render-user-data upload-user-data verify-user-data plan apply destroy

backup-state:
	@mkdir -p "$(BACKUP_DIR)"
	@stamp="$$(date +%Y%m%dT%H%M%S)_$$$$"; phase="$${BACKUP_PHASE:-snapshot}"; if [ -f "$(STATE_FILE)" ]; then cp "$(STATE_FILE)" "$(BACKUP_DIR)/$${stamp}-$${phase}-$(STATE_FILE)"; fi

init:
	$(TOFU) init -backend=false

fmt:
	$(TOFU) fmt -recursive

validate: init
	$(TOFU) validate

render-user-data:
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init render --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)"

upload-user-data: render-user-data
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init upload --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

verify-user-data: render-user-data
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init verify --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

plan: render-user-data
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) plan

apply:
	$(MAKE) upload-user-data verify-user-data
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) apply
	$(MAKE) backup-state BACKUP_PHASE=after

destroy:
	$(MAKE) backup-state BACKUP_PHASE=before
	$(TOFU) destroy
	$(MAKE) backup-state BACKUP_PHASE=after
