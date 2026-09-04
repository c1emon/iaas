ROOT ?= $(abspath .)
ASTRA ?= $(ROOT)/environments/astra
AUTOMATION ?= $(ROOT)/automation
PVE_DIR ?= $(ASTRA)/opentofu/pve
INVENTORY_DIR ?= $(ASTRA)/inventory
GENERATED_DIR ?= $(ASTRA)/generated
ANSIBLE_CONFIG ?= $(AUTOMATION)/ansible/ansible.cfg
ANSIBLE_INVENTORY ?= $(GENERATED_DIR)/ansible/pve.yml
ANSIBLE_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/pve/verify-guests.yml
ANSIBLE_BOOTSTRAP_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/pve/bootstrap-guests.yml
ANSIBLE_LIMIT ?= pve_vms
ANSIBLE_ARGS ?=
UV ?= uv
TOFU ?= tofu
GITLEAKS ?= gitleaks
PYTHON ?= PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" python
ANSIBLE_LINT_PATHS ?= $(AUTOMATION)/ansible/playbooks/pve $(AUTOMATION)/ansible/playbooks/opnsense $(AUTOMATION)/ansible/roles/vm_baseline
PACKER_BUILD_SCRIPT ?= $(AUTOMATION)/packer/proxmox/debian-13/build-template.sh
TEMPLATE_BUILD_ENV ?= $(GENERATED_DIR)/packer/debian-13.env
PVE_TFVARS ?= $(GENERATED_DIR)/opentofu/pve.tfvars.json
PVE_DOCS ?= $(GENERATED_DIR)/docs/pve-vms.md
SERVICES_DOCS ?= $(GENERATED_DIR)/docs/services.md
FOUNDATION_DOCS ?= $(GENERATED_DIR)/docs/foundation-recovery.md
PVE_USER_DATA_DIR ?= $(ROOT)/.cache/pve-cloud-init/user-data
BACKUP_DIR ?= $(ROOT)/.cache/tofu-state-backups

.PHONY: generate check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate check secret-scan ansible-syntax pve-generate pve-check services-generate services-check foundation-generate foundation-check foundation-health pve-validate pve-fmt pve-preflight pve-health pve-packer-build pve-plan pve-apply pve-destroy pve-verify-guests pve-bootstrap-guests pve-bootstrap-guests-syntax pve-ansible-syntax pve-backup-state render-cloud-init upload-cloud-init verify-cloud-init

generate: pve-generate services-generate foundation-generate

check-generated: pve-check services-check foundation-check

test:
	PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" pytest

lint-yaml:
	$(UV) run --directory "$(ROOT)" yamllint "$(INVENTORY_DIR)" "$(ASTRA)/ansible"

typecheck:
	PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" pyright

ansible-lint:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-lint $(ANSIBLE_LINT_PATHS)

tofu-fmt:
	$(TOFU) -chdir="$(AUTOMATION)/opentofu" fmt -recursive -check -diff
	$(TOFU) -chdir="$(PVE_DIR)" fmt -recursive -check -diff

tofu-validate: pve-validate

opnsense-validate:
	$(PYTHON) -m iaas_automation.opnsense_validation --vars-dir "$(ASTRA)/ansible/vars/opnsense"

check: check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate

secret-scan:
	@command -v "$(GITLEAKS)" >/dev/null 2>&1 || { printf 'error: gitleaks is required for secret-scan (install gitleaks or set GITLEAKS=/path/to/gitleaks)\n' >&2; exit 127; }
	$(GITLEAKS) detect --source "$(ROOT)" --config "$(ROOT)/.gitleaks.toml" --no-banner --redact

ansible-syntax: pve-ansible-syntax

pve-generate:
	$(PYTHON) -m iaas_automation.pve_inventory.cli --cluster "$(INVENTORY_DIR)/pve-cluster.yml" --vms "$(INVENTORY_DIR)/vms.yml" --tfvars "$(PVE_TFVARS)" --ansible "$(ANSIBLE_INVENTORY)" --docs "$(PVE_DOCS)" --template-build-env "$(TEMPLATE_BUILD_ENV)" --generate

pve-check:
	$(PYTHON) -m iaas_automation.pve_inventory.cli --cluster "$(INVENTORY_DIR)/pve-cluster.yml" --vms "$(INVENTORY_DIR)/vms.yml" --tfvars "$(PVE_TFVARS)" --ansible "$(ANSIBLE_INVENTORY)" --docs "$(PVE_DOCS)" --template-build-env "$(TEMPLATE_BUILD_ENV)" --check

services-generate:
	$(PYTHON) -m iaas_automation.services_inventory.cli --services "$(INVENTORY_DIR)/services.yml" --vms "$(INVENTORY_DIR)/vms.yml" --docs "$(SERVICES_DOCS)" --generate

services-check:
	$(PYTHON) -m iaas_automation.services_inventory.cli --services "$(INVENTORY_DIR)/services.yml" --vms "$(INVENTORY_DIR)/vms.yml" --docs "$(SERVICES_DOCS)" --check

foundation-generate:
	$(PYTHON) -m iaas_automation.foundation_inventory.cli --inventory "$(INVENTORY_DIR)/foundation.yml" --docs "$(FOUNDATION_DOCS)" --generate

foundation-check:
	$(PYTHON) -m iaas_automation.foundation_inventory.cli --inventory "$(INVENTORY_DIR)/foundation.yml" --docs "$(FOUNDATION_DOCS)" --check

foundation-health:
	$(PYTHON) -m iaas_automation.foundation_inventory.cli --inventory "$(INVENTORY_DIR)/foundation.yml" --health

pve-validate: pve-check
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-inventory -i "$(ANSIBLE_INVENTORY)" --list >/dev/null
	$(TOFU) -chdir="$(PVE_DIR)" init -backend=false
	$(TOFU) -chdir="$(PVE_DIR)" validate

pve-fmt:
	$(TOFU) -chdir="$(PVE_DIR)" fmt -recursive

pve-preflight:
	$(PYTHON) -m iaas_automation.pve_inventory.preflight --cluster "$(INVENTORY_DIR)/pve-cluster.yml" --vms "$(INVENTORY_DIR)/vms.yml"

pve-health:
	$(PYTHON) -m iaas_automation.pve_inventory.health --cluster "$(INVENTORY_DIR)/pve-cluster.yml" --vms "$(INVENTORY_DIR)/vms.yml"

pve-packer-build:
	TEMPLATE_BUILD_ENV="$(TEMPLATE_BUILD_ENV)" bash "$(PACKER_BUILD_SCRIPT)"

require-storage-id:
	@test -n "$(STORAGE_ID)" || { printf 'error: STORAGE_ID is required\n' >&2; exit 1; }

require-pve-target: require-storage-id
	@test -n "$(PVE_HOST)" || { printf 'error: PVE_HOST is required\n' >&2; exit 1; }
	@test -n "$(PVE_SSH_USER)" || { printf 'error: PVE_SSH_USER is required\n' >&2; exit 1; }

render-cloud-init: require-storage-id
	$(PYTHON) -m iaas_automation.pve_inventory.cloud_init render --tfvars "$(PVE_TFVARS)" --output-dir "$(PVE_USER_DATA_DIR)" --storage-id "$(STORAGE_ID)"

upload-cloud-init: require-pve-target
	$(PYTHON) -m iaas_automation.pve_inventory.cloud_init upload --tfvars "$(PVE_TFVARS)" --output-dir "$(PVE_USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

verify-cloud-init: require-pve-target
	$(PYTHON) -m iaas_automation.pve_inventory.cloud_init verify --tfvars "$(PVE_TFVARS)" --output-dir "$(PVE_USER_DATA_DIR)" --storage-id "$(STORAGE_ID)" --pve-host "$(PVE_HOST)" --ssh-user "$(PVE_SSH_USER)"

pve-backup-state:
	@mkdir -p "$(BACKUP_DIR)"
	@stamp="$$(date +%Y%m%dT%H%M%S)_$$$$"; phase="$${BACKUP_PHASE:-snapshot}"; if [ -f "$(PVE_DIR)/terraform.tfstate" ]; then cp "$(PVE_DIR)/terraform.tfstate" "$(BACKUP_DIR)/$${stamp}-$${phase}-terraform.tfstate"; fi

pve-plan: render-cloud-init
	$(MAKE) pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" plan -var-file="$(PVE_TFVARS)"

pve-apply: render-cloud-init upload-cloud-init verify-cloud-init
	$(MAKE) pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" apply -var-file="$(PVE_TFVARS)"
	$(MAKE) pve-backup-state BACKUP_PHASE=after

pve-destroy:
	$(MAKE) pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" destroy -var-file="$(PVE_TFVARS)"
	$(MAKE) pve-backup-state BACKUP_PHASE=after

pve-verify-guests:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"

pve-bootstrap-guests:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(ANSIBLE_INVENTORY)" -l "$(ANSIBLE_LIMIT)" $(ANSIBLE_ARGS) "$(ANSIBLE_BOOTSTRAP_PLAYBOOK)"

pve-bootstrap-guests-syntax:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(ANSIBLE_INVENTORY)" -l "$(ANSIBLE_LIMIT)" $(ANSIBLE_ARGS) "$(ANSIBLE_BOOTSTRAP_PLAYBOOK)"

pve-ansible-syntax:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"
