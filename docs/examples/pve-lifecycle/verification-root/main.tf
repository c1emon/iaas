terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.111.0"
    }
  }
}

resource "proxmox_virtual_environment_vm" "synthetic" {
  name      = "synthetic-delete-check"
  node_name = "synthetic-node"
  vm_id     = 501
  started   = false
}
