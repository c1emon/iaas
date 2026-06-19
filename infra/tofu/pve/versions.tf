terraform {
  required_version = ">= 1.6.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.109.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}
