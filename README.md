# Astra Infrastructure Automation

本仓库包含 Astra 环境声明与可复用基础设施自动化。完整的人类操作流程、参数解释、
准入、变更和验收要求仅以
[《Astra 基础设施操作手册》](docs/operations/README.md) 为准；不要从模块目录
README、设计文档或历史 OpenSpec 记录拼接第二套操作步骤。

不提交真实秘密、本地 state、cache、原始 export 或受保护 runtime 文件内容。

## 安全起点

```bash
uv sync --locked --dev
make generate
make check
make secret-scan
```

这些是离线安全门禁，不联系或改变 PVE、OPNsense、交换机、VM、Packer 或 K3s。
真实环境操作必须从手册的对应章节开始。

## 仓库层次

- `environments/astra/` — Astra-owned inventory, Ansible data, runtime
  templates, OpenTofu root, and committed generated outputs.
- `automation/` — reusable Python (`src/iaas_automation`), Ansible, OpenTofu
  modules, Packer, and PVE-node mechanisms.
- `platform/` — reserved for future in-cluster platform automation; no K3s or
  cluster platform capability is implemented here.
- `tests/` — repository tests.

## Astra 源与生成物

| Source | Purpose |
| --- | --- |
| `environments/astra/inventory/pve-cluster.yml` | PVE topology, networks, storage roles, templates, VMID policy, and PCI mappings. |
| `environments/astra/inventory/vms.yml` | VM declarations and lifecycle intent. |
| `environments/astra/inventory/services.yml` | Service metadata. |
| `environments/astra/inventory/foundation.yml` | Foundation recovery metadata. |
| `environments/astra/ansible/` | Environment inventory, group variables, and desired-state variables. |

Generated, reviewable non-secret artifacts are under
`environments/astra/generated/{opentofu,ansible,packer,docs}/`.

## 文档

- [唯一操作手册](docs/operations/README.md)
- [文档索引与架构/历史背景](docs/README.md)
- [可复用自动化实现边界](automation/README.md)
- [未来 in-cluster platform 边界](platform/README.md)
