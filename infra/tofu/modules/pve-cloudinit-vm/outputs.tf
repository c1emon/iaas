output "vm_id" {
  value = try(proxmox_virtual_environment_vm.protected[0].vm_id, proxmox_virtual_environment_vm.unprotected[0].vm_id)
}

output "name" {
  value = try(proxmox_virtual_environment_vm.protected[0].name, proxmox_virtual_environment_vm.unprotected[0].name)
}
