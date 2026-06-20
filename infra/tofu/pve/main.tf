provider "proxmox" {
  endpoint = var.pve_endpoint
  insecure = var.pve_insecure

  api_token = local.pve_api_token

  ssh {
    agent    = true
    username = var.pve_ssh_username
  }
}

module "long_lived_vms" {
  source   = "../modules/pve-cloudinit-vm"
  for_each = local.long_lived_vms

  cluster_name      = local.cluster.name
  disk_datastore_id = each.value.storage.disk_datastore_id
  template          = each.value.template
  vm                = each.value
  tags              = local.vm_tags[each.key]
  user_data_file_id = local.user_data_file_ids[each.key]
  prevent_destroy   = true
  started           = each.value.boot.started
  on_boot           = each.value.boot.on_boot
}

module "ephemeral_vms" {
  source   = "../modules/pve-cloudinit-vm"
  for_each = local.ephemeral_vms

  cluster_name      = local.cluster.name
  disk_datastore_id = each.value.storage.disk_datastore_id
  template          = each.value.template
  vm                = each.value
  tags              = local.vm_tags[each.key]
  user_data_file_id = local.user_data_file_ids[each.key]
  prevent_destroy   = false
  started           = each.value.boot.started
  on_boot           = each.value.boot.on_boot
}
