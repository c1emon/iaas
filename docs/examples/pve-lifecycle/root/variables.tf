variable "pve_endpoint" {
  type        = string
  description = "Credential-free HTTPS API endpoint selected by the caller."
}

variable "pve_insecure" {
  type        = bool
  description = "Synthetic example only; production must review this explicitly."
}

variable "pve_api_username" {
  type      = string
  sensitive = true
  ephemeral = true
}

variable "pve_api_token_id" {
  type      = string
  sensitive = true
  ephemeral = true
}

variable "pve_api_token_secret" {
  type      = string
  sensitive = true
  ephemeral = true
}

variable "pve_ssh_username" {
  type      = string
  sensitive = true
  ephemeral = true
}

variable "pve_ssh_private_key" {
  type      = string
  sensitive = true
  ephemeral = true
}
