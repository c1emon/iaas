packer {
  required_version = ">= 1.7.0"
}

# The first template foundation uses the genericcloud import workflow.
# The build logic lives in build-template.sh and sources the generated
# template-build.env; this file keeps the project ready for future
# Packer-driven orchestration without changing ownership.

variable "pve_endpoint" {
  type        = string
  description = "PVE API endpoint or node SSH target; local wrapper still requires explicit PVE_HOST"
}

variable "pve_node" {
  type        = string
  description = "Default build node, usually cohe"
  default     = "cohe"
}

variable "import_storage" {
  type        = string
  description = "PVE storage for ISO/import/snippet artifacts"
  default     = "images"
}

variable "disk_storage" {
  type        = string
  description = "PVE storage for VM/template disks"
  default     = "memory"
}

variable "template_vmid" {
  type        = number
  description = "Template VMID, constrained to the template range and typically sourced from template-build.env"
}

variable "template_name" {
  type        = string
  description = "Template name using the conservative wrapper regex; typically sourced from template-build.env"
}

variable "pve_username" {
  type        = string
  description = "PVE username for API or SSH context"
}

variable "pve_token_id" {
  type        = string
  description = "PVE API token id"
  sensitive   = true
}

variable "pve_token_secret" {
  type        = string
  description = "PVE API token secret"
  sensitive   = true
}

variable "cache_dir" {
  type        = string
  description = "Local cache under .cache/packer"
  default     = ".cache/packer"
}

variable "force_replace" {
  type        = bool
  description = "Allow replacing an existing dated template"
  default     = false
}

variable "image_url" {
  type        = string
  description = "Pinned Debian 13 genericcloud qcow2 URL, usually generated into template-build.env"
}

variable "image_sha512" {
  type        = string
  description = "Pinned SHA512 checksum for the qcow2 image, usually generated into template-build.env"
}
