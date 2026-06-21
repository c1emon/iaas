"""Default repository paths for the PVE inventory tool."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLUSTER = ROOT / "inventory" / "pve-cluster.yml"
DEFAULT_VMS = ROOT / "inventory" / "vms.yml"
DEFAULT_TFVARS = ROOT / "infra" / "tofu" / "pve" / "generated.auto.tfvars.json"
DEFAULT_ANSIBLE = ROOT / "ansible" / "inventories" / "generated" / "pve.yml"
DEFAULT_DOCS = ROOT / "docs" / "generated" / "pve-vms.md"
DEFAULT_TEMPLATE_BUILD_ENV = ROOT / "infra" / "packer" / "proxmox" / "debian-13" / "template-build.env"
DEFAULT_USER_DATA_DIR = ROOT / ".cache" / "pve-cloud-init" / "user-data"
