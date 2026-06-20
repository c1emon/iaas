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
  disk_datastore_id = local.disk_datastore
  default_template  = local.default_template
  vm_defaults       = local.vm_defaults
  vm                = each.value
  tags              = local.vm_tags[each.key]
  user_data_file_id = local.user_data_file_ids[each.key]
  prevent_destroy   = true
  started           = true
  on_boot           = true
}

module "ephemeral_vms" {
  source   = "../modules/pve-cloudinit-vm"
  for_each = local.ephemeral_vms

  cluster_name      = local.cluster.name
  disk_datastore_id = local.disk_datastore
  default_template  = local.default_template
  vm_defaults       = local.vm_defaults
  vm                = each.value
  tags              = local.vm_tags[each.key]
  user_data_file_id = local.user_data_file_ids[each.key]
  prevent_destroy   = false
  started           = true
  on_boot           = false
}
