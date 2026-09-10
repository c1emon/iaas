ROOT ?= $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RUNTIME_MAKEFILE := $(abspath $(lastword $(MAKEFILE_LIST)))
ifneq ($(origin ASTRA),undefined)
$(error ASTRA is no longer supported; set ENVIRONMENT_DIR and OUTPUT_DIR explicitly)
endif
ENVIRONMENT_DIR ?=
OUTPUT_DIR ?=
AUTOMATION ?= $(ROOT)/automation
PVE_DIR ?=
INVENTORY_DIR ?= $(ENVIRONMENT_DIR)/inventory
GENERATED_DIR ?= $(OUTPUT_DIR)/generated
RUNTIME_DIR ?= $(OUTPUT_DIR)/runtime
ANSIBLE_CONFIG ?= $(AUTOMATION)/ansible/ansible.cfg
ANSIBLE_INVENTORY ?= $(GENERATED_DIR)/ansible/pve.yml
ANSIBLE_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/pve/verify-guests.yml
ANSIBLE_BOOTSTRAP_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/pve/bootstrap-guests.yml
ANSIBLE_LIMIT ?= pve_vms
ANSIBLE_ARGS ?=
VM_BASELINE_EGRESS_POLICY ?=
VM_BASELINE_EGRESS_RUNTIME_SECRETS ?=
UV ?= uv
TOFU ?= tofu
GITLEAKS ?= gitleaks
RUNTIME_IMAGE ?= iaas-runtime:oci-release-test
PYTHON ?= PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" python
ANSIBLE_LINT_PATHS ?= $(AUTOMATION)/ansible/playbooks/pve $(AUTOMATION)/ansible/playbooks/opnsense $(AUTOMATION)/ansible/roles/vm_baseline
PACKER_BUILD_SCRIPT ?= $(AUTOMATION)/packer/proxmox/debian-13/build-template.sh
TEMPLATE_BUILD_ENV ?= $(GENERATED_DIR)/packer/debian-13.env
PVE_TFVARS ?= $(GENERATED_DIR)/opentofu/pve.tfvars.json
PVE_DOCS ?= $(GENERATED_DIR)/docs/pve-vms.md
SERVICES_DOCS ?= $(GENERATED_DIR)/docs/services.md
FOUNDATION_DOCS ?= $(GENERATED_DIR)/docs/foundation-recovery.md
PVE_USER_DATA_DIR ?= $(RUNTIME_DIR)/pve-cloud-init/user-data
BACKUP_DIR ?= $(RUNTIME_DIR)/tofu-state-backups
K3S_INTENT ?=
K3S_INVENTORY ?=
K3S_REVIEW ?= $(RUNTIME_DIR)/k3s/review.yml
K3S_SCOPE ?=
K3S_ANSIBLE_LIMIT = localhost,$(K3S_SCOPE)
K3S_RUNTIME_SECRETS ?=
K3S_PREFLIGHT_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/preflight.yml
K3S_VERIFY_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/verify.yml
K3S_DEPLOY_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/deploy.yml
K3S_SNAPSHOT_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/snapshot.yml
K3S_UPGRADE_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/upgrade.yml
K3S_UPGRADE_TARGET ?=
K3S_OBSERVED_VERSIONS ?=
K3S_UPGRADE_PLAN ?= $(RUNTIME_DIR)/k3s/upgrade-plan.json
PLATFORM_HANDOFF_INTENT ?=
PLATFORM_HANDOFF_OUTPUT ?=
PLATFORM_HANDOFF_PLAYBOOK ?= $(AUTOMATION)/ansible/playbooks/k3s/platform-handoff.yml

export ANSIBLE_ROLES_PATH := $(AUTOMATION)/ansible/roles
export ANSIBLE_COLLECTIONS_PATH := $(AUTOMATION)/ansible/collections
export ANSIBLE_FILTER_PLUGINS := $(AUTOMATION)/ansible/filter_plugins
export ANSIBLE_LOOKUP_PLUGINS := $(AUTOMATION)/ansible/plugins/lookup
export ENVIRONMENT_DIR OUTPUT_DIR

.DEFAULT_GOAL := help
.PHONY: runtime-build runtime-smoke runtime-tofu-check
runtime-build:
	sh "$(AUTOMATION)/runtime/build.sh" "$(RUNTIME_IMAGE)"

runtime-smoke:
	$(UV) run --directory "$(ROOT)" python "$(AUTOMATION)/runtime/smoke.py" --image "$(RUNTIME_IMAGE)"

runtime-tofu-check:
	$(UV) run --directory "$(ROOT)" python "$(AUTOMATION)/runtime/smoke.py" --image "$(RUNTIME_IMAGE)" --tofu

.PHONY: help require-environment require-pve-dir
help:
	@printf '%s\n' 'IaaS operations: pve-generate pve-check services-generate services-check foundation-generate foundation-check k3s-check k3s-render' 'Select ENVIRONMENT_DIR and OUTPUT_DIR for environment operations; PVE_DIR selects an external OpenTofu root.' 'Checkout validation: check test secret-scan'

require-environment:
	@test -n "$(ENVIRONMENT_DIR)" || { printf 'error: ENVIRONMENT_DIR is required\n' >&2; exit 1; }
	@test -d "$(ENVIRONMENT_DIR)" || { printf 'error: ENVIRONMENT_DIR must exist\n' >&2; exit 1; }
	@test -n "$(OUTPUT_DIR)" || { printf 'error: OUTPUT_DIR is required\n' >&2; exit 1; }
	@$(PYTHON) -m iaas_automation.runtime_paths --environment "$(ENVIRONMENT_DIR)" --implementation "$(AUTOMATION)" --output "$(OUTPUT_DIR)" --output "$(GENERATED_DIR)" --output "$(RUNTIME_DIR)" --output "$(PVE_TFVARS)" --output "$(ANSIBLE_INVENTORY)" --output "$(PVE_DOCS)" --output "$(TEMPLATE_BUILD_ENV)" --output "$(SERVICES_DOCS)" --output "$(FOUNDATION_DOCS)" --output "$(PVE_USER_DATA_DIR)" --output "$(BACKUP_DIR)"

require-pve-dir:
	@test -n "$(PVE_DIR)" || { printf 'error: PVE_DIR is required\n' >&2; exit 1; }
	@test -d "$(PVE_DIR)" || { printf 'error: PVE_DIR must exist\n' >&2; exit 1; }

pve-generate pve-check services-generate services-check foundation-generate foundation-check foundation-health pve-preflight pve-health lint-yaml opnsense-validate: require-environment
pve-validate pve-fmt tofu-fmt pve-plan pve-apply pve-destroy pve-backup-state: require-pve-dir

.PHONY: require-output require-k3s-output
require-output:
	@test -n "$(OUTPUT_DIR)" || { printf 'error: OUTPUT_DIR is required\n' >&2; exit 1; }
	@$(PYTHON) -m iaas_automation.runtime_paths --implementation "$(AUTOMATION)" $(if $(ENVIRONMENT_DIR),--environment "$(ENVIRONMENT_DIR)") --output "$(OUTPUT_DIR)" --output "$(RUNTIME_DIR)" --output "$(PVE_USER_DATA_DIR)" --output "$(BACKUP_DIR)"

require-k3s-output: require-output
	@$(PYTHON) -m iaas_automation.runtime_paths --implementation "$(AUTOMATION)" --input "$(K3S_INTENT)" --input "$(K3S_INVENTORY)" --output "$(K3S_REVIEW)" --output "$(K3S_UPGRADE_PLAN)" $(if $(PLATFORM_HANDOFF_INTENT),--input "$(PLATFORM_HANDOFF_INTENT)") $(if $(PLATFORM_HANDOFF_OUTPUT),--output "$(PLATFORM_HANDOFF_OUTPUT)")

render-cloud-init upload-cloud-init verify-cloud-init pve-backup-state: require-output
k3s-render: require-k3s-output

.PHONY: generate check-generated test lint-yaml typecheck ansible-lint tofu-fmt tofu-validate opnsense-validate check secret-scan ansible-syntax pve-generate pve-check services-generate services-check foundation-generate foundation-check foundation-health pve-validate pve-fmt pve-preflight pve-health pve-packer-build pve-plan pve-apply pve-destroy pve-verify-guests pve-bootstrap-guests pve-bootstrap-guests-syntax pve-ansible-syntax pve-backup-state render-cloud-init upload-cloud-init verify-cloud-init require-k3s-inputs require-k3s-scoped-inputs require-k3s-online-inputs require-k3s-upgrade-inputs require-platform-handoff-inputs require-platform-handoff-render-inputs k3s-check k3s-render k3s-ansible-syntax k3s-ansible-lint k3s-preflight k3s-verify k3s-deploy k3s-snapshot k3s-upgrade platform-handoff-check platform-handoff-render

generate: pve-generate services-generate foundation-generate

check-generated: pve-check services-check foundation-check

test:
	PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" pytest

lint-yaml:
	$(UV) run --directory "$(ROOT)" yamllint "$(INVENTORY_DIR)" "$(ENVIRONMENT_DIR)/ansible"

typecheck:
	PYTHONPATH="$(AUTOMATION)/src" $(UV) run --directory "$(ROOT)" pyright

ansible-lint:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-lint $(ANSIBLE_LINT_PATHS)

tofu-fmt:
	$(TOFU) -chdir="$(AUTOMATION)/opentofu" fmt -recursive -check -diff
	$(TOFU) -chdir="$(PVE_DIR)" fmt -recursive -check -diff

tofu-validate: pve-validate

opnsense-validate:
	$(PYTHON) -m iaas_automation.opnsense_validation --vars-dir "$(ENVIRONMENT_DIR)/ansible/vars/opnsense"

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

pve-plan:
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-check
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" render-cloud-init
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" plan -var-file="$(PVE_TFVARS)"

pve-apply:
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-check
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" render-cloud-init
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" upload-cloud-init
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" verify-cloud-init
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" apply -var-file="$(PVE_TFVARS)"
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-backup-state BACKUP_PHASE=after

pve-destroy:
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-backup-state BACKUP_PHASE=before
	$(TOFU) -chdir="$(PVE_DIR)" destroy -var-file="$(PVE_TFVARS)"
	$(MAKE) -f "$(RUNTIME_MAKEFILE)" pve-backup-state BACKUP_PHASE=after

pve-verify-guests:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"

pve-bootstrap-guests:
	@if [ -n "$(VM_BASELINE_EGRESS_POLICY)" ]; then test -f "$(VM_BASELINE_EGRESS_POLICY)" || { printf 'error: VM_BASELINE_EGRESS_POLICY must name a readable policy file\n' >&2; exit 1; }; fi
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(ANSIBLE_INVENTORY)" -l "$(ANSIBLE_LIMIT)" $(ANSIBLE_ARGS) -e "vm_baseline_egress_policy_file=$(VM_BASELINE_EGRESS_POLICY)" -e "vm_baseline_egress_runtime_secret_file=$(VM_BASELINE_EGRESS_RUNTIME_SECRETS)" "$(ANSIBLE_BOOTSTRAP_PLAYBOOK)"

pve-bootstrap-guests-syntax:
	@if [ -n "$(VM_BASELINE_EGRESS_POLICY)" ]; then test -f "$(VM_BASELINE_EGRESS_POLICY)" || { printf 'error: VM_BASELINE_EGRESS_POLICY must name a readable policy file\n' >&2; exit 1; }; fi
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(ANSIBLE_INVENTORY)" -l "$(ANSIBLE_LIMIT)" $(ANSIBLE_ARGS) -e "vm_baseline_egress_policy_file=$(VM_BASELINE_EGRESS_POLICY)" -e "vm_baseline_egress_runtime_secret_file=$(VM_BASELINE_EGRESS_RUNTIME_SECRETS)" "$(ANSIBLE_BOOTSTRAP_PLAYBOOK)"

pve-ansible-syntax:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(ANSIBLE_INVENTORY)" "$(ANSIBLE_PLAYBOOK)"

require-k3s-inputs:
	@test -n "$(K3S_INTENT)" || { printf 'error: K3S_INTENT is required\n' >&2; exit 1; }
	@test -n "$(K3S_INVENTORY)" || { printf 'error: K3S_INVENTORY is required\n' >&2; exit 1; }

require-k3s-scoped-inputs: require-k3s-inputs
	@test -n "$(K3S_SCOPE)" || { printf 'error: K3S_SCOPE is required for online K3s commands\n' >&2; exit 1; }

require-k3s-online-inputs: require-k3s-scoped-inputs
	@test -n "$(K3S_RUNTIME_SECRETS)" || { printf 'error: K3S_RUNTIME_SECRETS is required for online K3s commands\n' >&2; exit 1; }
	@test -f "$(K3S_RUNTIME_SECRETS)" || { printf 'error: K3S_RUNTIME_SECRETS must name a protected runtime secret file\n' >&2; exit 1; }

require-k3s-upgrade-inputs: require-k3s-online-inputs
	@test -n "$(K3S_UPGRADE_TARGET)" || { printf 'error: K3S_UPGRADE_TARGET is required for k3s-upgrade\n' >&2; exit 1; }
	@test -n "$(K3S_OBSERVED_VERSIONS)" || { printf 'error: K3S_OBSERVED_VERSIONS is required for k3s-upgrade\n' >&2; exit 1; }
	@test -f "$(K3S_OBSERVED_VERSIONS)" || { printf 'error: K3S_OBSERVED_VERSIONS must name a JSON observation file\n' >&2; exit 1; }

require-platform-handoff-inputs: require-k3s-scoped-inputs
	@test -n "$(PLATFORM_HANDOFF_INTENT)" || { printf 'error: PLATFORM_HANDOFF_INTENT is required\n' >&2; exit 1; }
	@test -f "$(PLATFORM_HANDOFF_INTENT)" || { printf 'error: PLATFORM_HANDOFF_INTENT must name a readable intent file\n' >&2; exit 1; }

require-platform-handoff-render-inputs: require-platform-handoff-inputs
	@test -n "$(PLATFORM_HANDOFF_OUTPUT)" || { printf 'error: PLATFORM_HANDOFF_OUTPUT is required\n' >&2; exit 1; }

k3s-check: require-k3s-inputs
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)"

k3s-render: require-k3s-inputs
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --render "$(K3S_REVIEW)"

k3s-ansible-syntax: require-k3s-inputs
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook --syntax-check -i "$(K3S_INVENTORY)" "$(K3S_PREFLIGHT_PLAYBOOK)"

k3s-ansible-lint:
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-lint "$(AUTOMATION)/ansible/playbooks/k3s" "$(AUTOMATION)/ansible/roles/k3s_acquisition" "$(AUTOMATION)/ansible/roles/k3s_agent" "$(AUTOMATION)/ansible/roles/k3s_preflight" "$(AUTOMATION)/ansible/roles/k3s_prerequisites" "$(AUTOMATION)/ansible/roles/k3s_runtime_config" "$(AUTOMATION)/ansible/roles/k3s_server" "$(AUTOMATION)/ansible/roles/k3s_snapshot" "$(AUTOMATION)/ansible/roles/k3s_upgrade" "$(AUTOMATION)/ansible/roles/k3s_verify"

k3s-preflight: require-k3s-online-inputs k3s-render
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --scope "$(K3S_SCOPE)" --runtime-secrets "$(K3S_RUNTIME_SECRETS)"
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "k3s_model_path=$(K3S_REVIEW)" -e "k3s_preflight_scope=$(K3S_SCOPE)" -e "k3s_runtime_secret_file=$(K3S_RUNTIME_SECRETS)" "$(K3S_PREFLIGHT_PLAYBOOK)"

k3s-verify: require-k3s-scoped-inputs k3s-render
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --scope "$(K3S_SCOPE)"
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "k3s_model_path=$(K3S_REVIEW)" -e "k3s_verify_scope=$(K3S_SCOPE)" "$(K3S_VERIFY_PLAYBOOK)"

k3s-deploy: require-k3s-online-inputs k3s-render
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --scope "$(K3S_SCOPE)" --whole-cluster-scope --runtime-secrets "$(K3S_RUNTIME_SECRETS)"
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "k3s_deploy_model_path=$(K3S_REVIEW)" -e "k3s_deploy_scope=$(K3S_SCOPE)" -e "k3s_deploy_runtime_secret_file=$(K3S_RUNTIME_SECRETS)" "$(K3S_DEPLOY_PLAYBOOK)"

k3s-snapshot: require-k3s-scoped-inputs k3s-render
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --scope "$(K3S_SCOPE)"
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "k3s_model_path=$(K3S_REVIEW)" -e "k3s_snapshot_scope=$(K3S_SCOPE)" "$(K3S_SNAPSHOT_PLAYBOOK)"

k3s-upgrade: require-k3s-upgrade-inputs k3s-render
	$(PYTHON) -m iaas_automation.k3s_automation --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --scope "$(K3S_SCOPE)" --upgrade-target "$(K3S_UPGRADE_TARGET)" --observed-versions "$(K3S_OBSERVED_VERSIONS)" --render-upgrade-plan "$(K3S_UPGRADE_PLAN)" --runtime-secrets "$(K3S_RUNTIME_SECRETS)"
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "k3s_upgrade_model_path=$(K3S_REVIEW)" -e "k3s_upgrade_scope=$(K3S_SCOPE)" -e "k3s_upgrade_target_version=$(K3S_UPGRADE_TARGET)" -e "k3s_upgrade_observed_versions_path=$(K3S_OBSERVED_VERSIONS)" -e "k3s_upgrade_plan_path=$(K3S_UPGRADE_PLAN)" -e "k3s_upgrade_runtime_secret_file=$(K3S_RUNTIME_SECRETS)" "$(K3S_UPGRADE_PLAYBOOK)"

platform-handoff-check: require-platform-handoff-inputs
	$(PYTHON) -m iaas_automation.platform_handoff --intent "$(K3S_INTENT)" --inventory "$(K3S_INVENTORY)" --handoff-intent "$(PLATFORM_HANDOFF_INTENT)" --scope "$(K3S_SCOPE)"

platform-handoff-render: require-platform-handoff-render-inputs k3s-verify
	ANSIBLE_CONFIG="$(ANSIBLE_CONFIG)" $(UV) run --directory "$(ROOT)" ansible-playbook -i "$(K3S_INVENTORY)" -l "$(K3S_ANSIBLE_LIMIT)" -e "platform_handoff_model_path=$(K3S_REVIEW)" -e "platform_handoff_k3s_intent=$(K3S_INTENT)" -e "platform_handoff_intent=$(PLATFORM_HANDOFF_INTENT)" -e "platform_handoff_scope=$(K3S_SCOPE)" -e "platform_handoff_output=$(PLATFORM_HANDOFF_OUTPUT)" "$(PLATFORM_HANDOFF_PLAYBOOK)"
