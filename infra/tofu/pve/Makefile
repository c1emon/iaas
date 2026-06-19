TOFU ?= tofu
UV ?= uv
ROOT ?= $(abspath ../../../)
STATE_FILE ?= terraform.tfstate
BACKUP_DIR ?= $(ROOT)/.cache/tofu-state-backups
USER_DATA_DIR ?= $(ROOT)/.cache/pve-cloud-init/user-data

.PHONY: backup-state init fmt validate require-storage-id require-pve-target render-user-data upload-user-data verify-user-data plan apply destroy

backup-state:
	@mkdir -p "$(BACKUP_DIR)"
	@stamp="$$(date +%Y%m%dT%H%M%S)_$$$$"; phase="$${BACKUP_PHASE:-snapshot}"; if [ -f "$(STATE_FILE)" ]; then cp "$(STATE_FILE)" "$(BACKUP_DIR)/$${stamp}-$${phase}-$(STATE_FILE)"; fi

init:
	$(TOFU) init -backend=false

fmt:
	$(TOFU) fmt -recursive

validate: init
	$(TOFU) validate

require-storage-id:
	@test -n "$(STORAGE_ID)" || { printf 'error: STORAGE_ID is required\n' >&2; exit 1; }

require-pve-target: require-storage-id
	@test -n "$(PVE_HOST)" || { printf 'error: PVE_HOST is required\n' >&2; exit 1; }
	@test -n "$(PVE_SSH_USER)" || { printf 'error: PVE_SSH_USER is required\n' >&2; exit 1; }

render-user-data: require-storage-id
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init render --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)"

upload-user-data: require-pve-target render-user-data
	$(UV) run --directory "$(ROOT)" python -m scripts.pve_inventory.cloud_init upload --output-dir "$(USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

verify-user-data: require-pve-target render-user-data
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
