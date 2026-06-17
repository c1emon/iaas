# PVE VMs

| Name | VMID | Lifecycle | Node | Network | IP | Groups | Tags | Passthrough |
|---|---:|---|---|---|---|---|---|---|
| dev-web-01 | 500 | ephemeral_lab | cohe | dev | 10.10.0.20/24 | dev, web | dev, web | no |
| prod-app-01 | 1000 | long_lived | cohe | prod | 10.50.0.20/24 | prod, app | prod, app | no |
| media-lab-01 | 501 | ephemeral_lab | cohe | dev | 10.10.0.21/24 | lab, media | lab, media, igpu | yes |

## Cluster defaults

- Default template: debian_13_genericcloud
- VM cores: 2
- VM memory MiB: 2048
- VM root disk GiB: 20
