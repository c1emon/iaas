locals {
  vm_is_protected    = var.prevent_destroy
  vm_passthrough     = try(var.vm.passthrough == null ? [] : var.vm.passthrough, [])
  vm_has_passthrough = length(local.vm_passthrough) > 0
}

resource "proxmox_virtual_environment_vm" "protected" {
  count = local.vm_is_protected ? 1 : 0

  name            = var.vm.name
  node_name       = var.vm.node
  vm_id           = var.vm.vmid
  started         = var.started
  on_boot         = var.on_boot
  bios            = var.template.bios
  machine         = var.template.machine
  tags            = var.tags
  description     = "Managed by OpenTofu for ${var.cluster_name}"
  scsi_hardware   = var.template.scsi_controller
  stop_on_destroy = true

  clone {
    node_name    = var.template.node
    vm_id        = var.template.vmid
    full         = true
    datastore_id = var.disk_datastore_id
  }

  cpu {
    cores = var.vm.resources.cores
    type  = var.template.cpu_type
  }

  memory {
    dedicated = var.vm.resources.memory_mib
  }

  disk {
    datastore_id = var.disk_datastore_id
    interface    = var.template.primary_disk
    size         = var.vm.resources.root_disk_gib
  }

  network_device {
    bridge = var.vm.network.bridge
  }

  dynamic "hostpci" {
    for_each = local.vm_passthrough

    content {
      device  = hostpci.value.device
      mapping = hostpci.value.mapping
      pcie    = hostpci.value.pcie
      rombar  = hostpci.value.rombar
      xvga    = hostpci.value.xvga
    }
  }

  initialization {
    datastore_id = var.cloud_init_datastore_id

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

    precondition {
      condition     = !local.vm_has_passthrough || (var.template.bios == "ovmf" && var.template.machine == "q35" && var.template.cpu_type == "host" && try(var.vm.ha.enabled, false) == false)
      error_message = "Passthrough VMs require q35, ovmf, cpu_type host, and HA disabled."
    }
  }
}

resource "proxmox_virtual_environment_vm" "unprotected" {
  count = local.vm_is_protected ? 0 : 1

  name            = var.vm.name
  node_name       = var.vm.node
  vm_id           = var.vm.vmid
  started         = var.started
  on_boot         = var.on_boot
  bios            = var.template.bios
  machine         = var.template.machine
  tags            = var.tags
  description     = "Managed by OpenTofu for ${var.cluster_name}"
  scsi_hardware   = var.template.scsi_controller
  stop_on_destroy = true

  clone {
    node_name    = var.template.node
    vm_id        = var.template.vmid
    full         = true
    datastore_id = var.disk_datastore_id
  }

  cpu {
    cores = var.vm.resources.cores
    type  = var.template.cpu_type
  }

  memory {
    dedicated = var.vm.resources.memory_mib
  }

  disk {
    datastore_id = var.disk_datastore_id
    interface    = var.template.primary_disk
    size         = var.vm.resources.root_disk_gib
  }

  network_device {
    bridge = var.vm.network.bridge
  }

  dynamic "hostpci" {
    for_each = local.vm_passthrough

    content {
      device  = hostpci.value.device
      mapping = hostpci.value.mapping
      pcie    = hostpci.value.pcie
      rombar  = hostpci.value.rombar
      xvga    = hostpci.value.xvga
    }
  }

  initialization {
    datastore_id = var.cloud_init_datastore_id

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

    precondition {
      condition     = !local.vm_has_passthrough || (var.template.bios == "ovmf" && var.template.machine == "q35" && var.template.cpu_type == "host" && try(var.vm.ha.enabled, false) == false)
      error_message = "Passthrough VMs require q35, ovmf, cpu_type host, and HA disabled."
    }
  }
}
