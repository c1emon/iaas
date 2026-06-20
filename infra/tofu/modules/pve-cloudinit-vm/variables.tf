variable "cluster_name" {
  type        = string
  description = "Cluster name for descriptive text."
}

variable "disk_datastore_id" {
  type        = string
  description = "Datastore used for the VM root disk."
}

variable "template" {
  type        = any
  description = "Template data from the cluster source-of-truth."
}

variable "vm" {
  type        = any
  description = "Single VM declaration from generated.auto.tfvars.json."
}

variable "started" {
  type        = bool
  description = "Whether the VM should be started after provisioning."
}

variable "tags" {
  type        = list(string)
  description = "Computed VM tags."
}

variable "user_data_file_id" {
  type        = string
  description = "Cloud-init user-data snippet file id such as images:snippets/opentofu-vm-500-user-data.yml."
}

variable "prevent_destroy" {
  type        = bool
  description = "Protect the VM from accidental destroy."
}

variable "on_boot" {
  type        = bool
  description = "Whether the VM should start on host boot."
}
