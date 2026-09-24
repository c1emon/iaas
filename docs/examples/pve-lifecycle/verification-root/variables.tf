variable "pve_endpoint" {
  type = string
}

variable "pve_insecure" {
  type = bool
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
