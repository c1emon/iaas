# PVE VMs

| Name | VMID | Lifecycle | Node | NIC | Network | MAC | IP | Gateway | Default route | Ansible conn | DNS | Template | Disk datastore | CPU | Memory | Disk | Started | On boot | Groups | Tags | Passthrough |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| dev-web-01 | 500 | ephemeral_lab | cohe | mgmt0 (management) | dev / br_dev | 52:54:00:00:01:f4 | 10.10.0.20/24 | 10.10.0.254 | yes | yes | 10.10.0.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | dev, web | dev, web | no |
| prod-app-01 | 1000 | long_lived | cohe | mgmt0 (management) | prod / br_prod | 52:54:00:00:03:e8 | 10.50.0.20/24 | 10.50.0.254 | yes | yes | 10.50.0.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | prod, app | prod, app | no |
| media-lab-01 | 501 | ephemeral_lab | cohe | mgmt0 (management) | dev / br_dev | 52:54:00:00:01:f5 | 10.10.0.21/24 | 10.10.0.254 | yes | yes | 10.10.0.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | lab, media | lab, media, igpu | hostpci0:iGpu0 (pcie=true, rombar=true, xvga=false) |

## Cluster defaults

- Default template: debian_13_genericcloud
- VM cores: 2
- VM memory MiB: 2048
- VM root disk GiB: 20
