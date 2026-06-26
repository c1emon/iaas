# PVE VMs

| Name | VMID | Lifecycle | Node | Network | IP | Template | Disk datastore | CPU | Memory | Disk | Started | On boot | Groups | Tags | Passthrough |
|---|---:|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| dev-web-01 | 500 | ephemeral_lab | cohe | dev | 10.10.0.20/24 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | dev, web | dev, web | no |
| prod-app-01 | 1000 | long_lived | cohe | prod | 10.50.0.20/24 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | prod, app | prod, app | no |
| media-lab-01 | 501 | ephemeral_lab | cohe | dev | 10.10.0.21/24 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | lab, media | lab, media, igpu | hostpci0:iGpu0 (pcie=true, rombar=true, xvga=false) |

## Cluster defaults

- Default template: debian_13_genericcloud
- VM cores: 2
- VM memory MiB: 2048
- VM root disk GiB: 20
