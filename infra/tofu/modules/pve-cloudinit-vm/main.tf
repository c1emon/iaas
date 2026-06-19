locals {
  vm_is_protected = var.prevent_destroy
}

resource "proxmox_virtual_environment_vm" "protected" {
  count = local.vm_is_protected ? 1 : 0

  name            = var.vm.name
  node_name       = var.vm.node
  vm_id           = var.vm.vmid
  on_boot         = var.on_boot
  bios            = var.vm_defaults.bios
  machine         = var.vm_defaults.machine
  tags            = var.tags
  description     = "Managed by OpenTofu for ${var.cluster_name}"
  scsi_hardware   = var.vm_defaults.scsi_controller
  stop_on_destroy = true

  clone {
    node_name = var.default_template.node
    vm_id     = var.default_template.vmid
    full      = true
  }

  cpu {
    cores = var.vm_defaults.cores
    type  = var.vm_defaults.cpu_type
  }

  memory {
    dedicated = var.vm_defaults.memory_mib
  }

  disk {
    datastore_id = var.disk_datastore_id
    interface    = var.vm_defaults.primary_disk
    size         = var.vm_defaults.root_disk_gib
  }

  network_device {
    bridge = var.vm.network.bridge
  }

  initialization {
    datastore_id = var.disk_datastore_id

    ip_config {
      ipv4 {
        address = var.vm.static_ip
        gateway = var.vm.gateway
      }
    }

    dns {
      servers = var.vm.dns
    }

    user_data_file_id = var.user_data_file_id
  }

  efi_disk {
    datastore_id = var.disk_datastore_id
    file_format  = "raw"
    type         = "4m"
  }

  agent {
    enabled = true
  }

  lifecycle {
    ignore_changes  = [initialization[0].user_data_file_id]
    prevent_destroy = true
  }
}

resource "proxmox_virtual_environment_vm" "unprotected" {
  count = local.vm_is_protected ? 0 : 1

  name            = var.vm.name
  node_name       = var.vm.node
  vm_id           = var.vm.vmid
  on_boot         = var.on_boot
  bios            = var.vm_defaults.bios
  machine         = var.vm_defaults.machine
  tags            = var.tags
  description     = "Managed by OpenTofu for ${var.cluster_name}"
  scsi_hardware   = var.vm_defaults.scsi_controller
  stop_on_destroy = true

  clone {
    node_name = var.default_template.node
    vm_id     = var.default_template.vmid
    full      = true
  }

  cpu {
    cores = var.vm_defaults.cores
    type  = var.vm_defaults.cpu_type
  }

  memory {
    dedicated = var.vm_defaults.memory_mib
  }

  disk {
    datastore_id = var.disk_datastore_id
    interface    = var.vm_defaults.primary_disk
    size         = var.vm_defaults.root_disk_gib
  }

  network_device {
    bridge = var.vm.network.bridge
  }

  initialization {
    datastore_id = var.disk_datastore_id

    ip_config {
      ipv4 {
        address = var.vm.static_ip
        gateway = var.vm.gateway
      }
    }

    dns {
      servers = var.vm.dns
    }

    user_data_file_id = var.user_data_file_id
  }

  efi_disk {
    datastore_id = var.disk_datastore_id
    file_format  = "raw"
    type         = "4m"
  }

  agent {
    enabled = true
  }

  lifecycle {
    ignore_changes = [initialization[0].user_data_file_id]
  }
}
