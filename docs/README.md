# Documentation Index

Use this index after the root [operator manual](../README.md). Do not commit
secrets, exported private configs, or unencrypted backups.

## Start here

- [Root operator manual](../README.md) — safe first commands, source-of-truth
  files, generated outputs, runtime parameters, and safety classes.

## Planning and roadmaps

- Historical/context: [Review remediation roadmap](review-remediation-roadmap.md)
- Historical/context: [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
- Planned consolidated roadmap entrypoint: `docs/roadmap.md` (tracked by `consolidate-documentation-roadmaps`; not present yet)

## Architecture and inventory

- [Architecture notes](architecture.md)
- [Service metadata schema and review rules](service-metadata.md)

## Operations and runbooks

- [PVE state, cache, and secret operations](pve-state-cache-secrets.md)
- [PVE PCI passthrough readiness](runbooks/pve-pci-passthrough-readiness.md)
- [PVE automation preflight decision](decisions/pve-automation-preflight.md)

## PVE

- [OpenTofu PVE VM lifecycle](../infra/tofu/pve/README.md)
- [Debian 13 PVE template foundation](../infra/packer/proxmox/debian-13/README.md)
- [Generated PVE VM summary](generated/pve-vms.md)

## OPNsense

- [OPNsense management plan](opnsense-management.md)
- [Ansible automation overview](../ansible/README.md)
- [OPNsense playbooks](../ansible/playbooks/opnsense/README.md)

## Switches

- [Switch playbooks](../ansible/playbooks/switches/README.md)
- [switch_config role](../ansible/roles/switch_config/README.md)

## Service metadata

- [Service metadata schema and review rules](service-metadata.md)
- [Generated service metadata](generated/services.md)

## Generated references

- [Generated service metadata](generated/services.md)
- [Generated PVE VM summary](generated/pve-vms.md)

## Decisions and historical context

- [PVE automation preflight decision](decisions/pve-automation-preflight.md)
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
- [Review remediation roadmap](review-remediation-roadmap.md)

## Other references

- [Repository scripts](../scripts/README.md)
