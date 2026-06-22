variable "cluster" {
  description = "Cluster source-of-truth data from generated.auto.tfvars.json."
  type        = any
}

variable "vms" {
  description = "VM declarations from generated.auto.tfvars.json."
  type        = any
}

variable "pve_endpoint" {
  description = "PVE API endpoint, typically injected through op run."
  type        = string
}

variable "pve_api_username" {
  description = "PVE API username, typically pve-ops@pve."
  type        = string
  default     = "pve-ops@pve"
}

variable "pve_api_token_id" {
  description = "PVE API token id, typically opentofu."
  type        = string
}

variable "pve_api_token_secret" {
  description = "PVE API token secret."
  type        = string
  sensitive   = true
}

variable "pve_insecure" {
  description = "Allow the PVE API TLS certificate to be self-signed."
  type        = bool
  default     = false
}

variable "pve_ssh_username" {
  description = "SSH username used by the provider on PVE nodes."
  type        = string
  default     = "pve-ops"
}
