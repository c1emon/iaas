terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.111.0"
    }
  }
}

locals {
  input = jsondecode(file("/output/generated/opentofu/pve.tfvars.json"))
  vm    = local.input.vms[0]
}

module "synthetic" {
  source = "/opt/iaas/automation/opentofu/modules/pve-cloudinit-vm"

  cluster_name            = local.input.cluster.name
  disk_datastore_id       = local.vm.storage.disk_datastore_id
  cloud_init_datastore_id = "synthetic-disks"
  template                = local.vm.template
  vm                      = local.vm
  tags                    = ["synthetic"]
  started                 = false
  on_boot                 = false
  prevent_destroy         = false
}
