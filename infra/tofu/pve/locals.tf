locals {
  cluster = var.cluster
  vms     = var.vms

  default_template_name = local.cluster.default_template
  default_template      = local.cluster.templates[local.default_template_name]
  vm_defaults           = local.cluster.vm_defaults
  memory_datastore      = local.cluster.storage_roles.memory.datastore

  vms_by_name = {
    for vm in local.vms : vm.name => vm
  }

  long_lived_vms = {
    for name, vm in local.vms_by_name : name => vm
    if lower(vm.lifecycle_class) == "long_lived" && try(vm.passthrough, null) == null
  }

  ephemeral_vms = {
    for name, vm in local.vms_by_name : name => vm
    if lower(vm.lifecycle_class) != "long_lived" && try(vm.passthrough, null) == null
  }

  deferred_passthrough_vms = {
    for name, vm in local.vms_by_name : name => vm
    if try(vm.passthrough, null) != null
  }

  cloud_init_vms     = merge(local.long_lived_vms, local.ephemeral_vms)
  snippets_datastore = local.cluster.storage_roles.images.datastore

  user_data_file_ids = {
    for name, vm in local.cloud_init_vms : name => "${local.snippets_datastore}:snippets/opentofu-vm-${vm.vmid}-user-data.yml"
  }

  vm_tags = {
    for name, vm in local.vms_by_name : name => distinct(compact(concat(
      ["managed-by-opentofu", vm.lifecycle_class, vm.network.name],
      try(vm.tags, [])
    )))
  }

  pve_api_token = "${var.pve_api_username}!${var.pve_api_token_id}=${var.pve_api_token_secret}"
}
