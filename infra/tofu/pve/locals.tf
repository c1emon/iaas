locals {
  cluster = var.cluster
  vms     = var.vms

  vms_by_name = {
    for vm in local.vms : vm.name => vm
  }

  long_lived_vms = {
    for name, vm in local.vms_by_name : name => vm
    if lower(vm.lifecycle_class) == "long_lived"
  }

  ephemeral_vms = {
    for name, vm in local.vms_by_name : name => vm
    if lower(vm.lifecycle_class) != "long_lived"
  }

  cloud_init_vms       = local.vms_by_name
  snippets_datastore   = local.cluster.storage_roles[local.cluster.automation.cloud_init.snippet_storage_role].datastore
  cloud_init_datastore = local.cluster.storage_roles[local.cluster.automation.cloud_init.drive_storage_role].datastore

  user_data_file_ids = {
    for name, vm in local.cloud_init_vms : name => "${local.snippets_datastore}:snippets/${local.cluster.automation.cloud_init.snippet_file_prefix}-${vm.vmid}-user-data.yml"
  }

  vm_tags = {
    for name, vm in local.vms_by_name : name => distinct(compact(concat(
      ["managed-by-opentofu", vm.lifecycle_class, vm.network.name],
      try(vm.tags, [])
    )))
  }

  pve_api_token = "${var.pve_api_username}!${var.pve_api_token_id}=${var.pve_api_token_secret}"
}
