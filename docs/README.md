# Documentation Index

Start with the [root operator manual](../README.md). Do not commit secrets,
local state, raw exports, or unencrypted backups.

## Current operations

- [Architecture notes](architecture.md)
- [PVE state, cache, and secret operations](pve-state-cache-secrets.md)
- [PVE rolling maintenance](runbooks/pve-rolling-maintenance.md)
- [PVE PCI passthrough readiness](runbooks/pve-pci-passthrough-readiness.md)
- [OPNsense management](opnsense-management.md)
- [Service metadata](service-metadata.md)
- [Astra OpenTofu root](../environments/astra/opentofu/pve/README.md)
- [Reusable Ansible automation](../automation/ansible/README.md)
- [Future platform boundary](../platform/README.md)

Committed generated references live under
`environments/astra/generated/docs/`:

- [PVE VMs](../environments/astra/generated/docs/pve-vms.md)
- [Services](../environments/astra/generated/docs/services.md)
- [Foundation recovery](../environments/astra/generated/docs/foundation-recovery.md)

## Historical context

- [Roadmap and backlog](roadmap.md)
- [PVE automation preflight decision](decisions/pve-automation-preflight.md)
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
- [Review remediation roadmap](review-remediation-roadmap.md)

These historical documents may use paths that predate the repository-layer
cutover; current commands and paths are defined by the root operator manual.
