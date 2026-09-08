# PVE VMs

| Name | VMID | Lifecycle | Node | NIC | Network | MAC | IP | Gateway | Default route | Ansible conn | DNS | Template | Disk datastore | CPU | Memory | Disk | Started | On boot | Groups | Tags | Passthrough |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| dev-web-01 | 500 | ephemeral_lab | node-a | mgmt0 (management) | dev / br_dev | 52:54:00:00:01:f4 | 198.51.100.20/24 | 198.51.100.254 | yes | yes | 198.51.100.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | dev, web | dev, web | no |
| prod-app-01 | 1000 | long_lived | node-a | mgmt0 (management) | prod / br_prod | 52:54:00:00:03:e8 | 203.0.113.20/24 | 203.0.113.254 | yes | yes | 203.0.113.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | prod, app | prod, app | no |
| media-lab-01 | 501 | ephemeral_lab | node-a | mgmt0 (management) | dev / br_dev | 52:54:00:00:01:f5 | 198.51.100.21/24 | 198.51.100.254 | yes | yes | 198.51.100.254 | debian_13_genericcloud (9001) | memory | 2 | 2048 | 20 | no | no | lab, media | lab, media, igpu | hostpci0:test-gpu (pcie=true, rombar=true, xvga=false) |

## Cluster defaults

- Default template: debian_13_genericcloud
- VM cores: 2
- VM memory MiB: 2048
- VM root disk GiB: 20
