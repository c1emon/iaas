packer {
  required_version = ">= 1.16.0"

  required_plugins {
    qemu = {
      version = "= 1.1.3"
      source  = "github.com/hashicorp/qemu"
    }
    ansible = {
      version = "= 1.1.6"
      source  = "github.com/hashicorp/ansible"
    }
  }
}

variable "base_image" { type = string }
variable "base_checksum" { type = string }
variable "output_directory" { type = string }
variable "firmware" { type = string }
variable "seed_directory" { type = string }
variable "ssh_username" { type = string }
variable "ssh_private_key_file" { type = string }
variable "apt_mirror" { type = string }
variable "apt_security_mirror" { type = string }
variable "packages" {
  type    = string
  default = "[]"
}
variable "timezone" {
  type    = string
  default = "UTC"
}
variable "locale" {
  type    = string
  default = "C.UTF-8"
}
variable "cloud_init" {
  type    = string
  default = "installed"
}
variable "guest_agent" {
  type    = string
  default = "installed"
}
variable "uefi_code" {
  type    = string
  default = ""
}
variable "uefi_vars" {
  type    = string
  default = ""
}
variable "cpus" { type = number }
variable "memory_mib" { type = number }

source "qemu" "debian-13-amd64" {
  iso_url              = var.base_image
  iso_checksum         = var.base_checksum
  disk_image           = true
  output_directory     = var.output_directory
  vm_name              = "disk.qcow2"
  format               = "qcow2"
  accelerator          = "kvm"
  qemu_binary          = "qemu-system-x86_64"
  cpus                 = var.cpus
  memory               = var.memory_mib
  machine_type         = "q35"
  headless             = true
  ssh_username         = var.ssh_username
  ssh_private_key_file = var.ssh_private_key_file
  ssh_timeout          = "20m"
  shutdown_command     = "sudo -n /sbin/shutdown -P now"
  boot_wait            = "5s"
  net_device           = "virtio-net"
  disk_interface       = "virtio"
  vnc_bind_address     = "127.0.0.1"
  # Native EFI/CD fields preserve Packer's generated system-disk -drive.
  # qemuargs is deliberately absent: any -drive override replaces defaults.
  efi_boot          = var.firmware == "uefi"
  efi_firmware_code = var.firmware == "uefi" ? var.uefi_code : null
  efi_firmware_vars = var.firmware == "uefi" ? var.uefi_vars : null
  efi_drop_efivars  = true
  # _make_seed namespaces the host files by phase, but NoCloud requires the
  # exact root names user-data and meta-data on the attached ISO.
  cd_content = {
    "user-data" = file("${var.seed_directory}/build.user-data")
    "meta-data" = file("${var.seed_directory}/build.meta-data")
  }
  cd_label = "cidata"
}

build {
  sources = ["source.qemu.debian-13-amd64"]

  provisioner "ansible" {
    playbook_file = "${path.root}/ansible/customize.yml"
    user          = var.ssh_username
    extra_arguments = [
      "--extra-vars", "apt_mirror=${var.apt_mirror}",
      "--extra-vars", "apt_security_mirror=${var.apt_security_mirror}",
      "--extra-vars", "packages_json=${var.packages}",
      "--extra-vars", "image_timezone=${var.timezone}",
      "--extra-vars", "image_locale=${var.locale}",
      "--extra-vars", "image_cloud_init=${var.cloud_init}",
      "--extra-vars", "image_guest_agent=${var.guest_agent}",
    ]
  }
}
