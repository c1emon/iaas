# IaaS Infrastructure Automation

本仓库交付跨环境复用的基础设施自动化和版本化 OCI 运行镜像。
调用方提供环境声明、输出目录、OpenTofu root 与已解析凭据；运行时不选择默认环境。
完整的人类操作流程、参数解释、
准入、变更和验收要求仅以
[《IaaS 基础设施操作手册》](docs/operations/README.md) 为准；不要从模块目录
README、设计文档或历史 OpenSpec 记录拼接第二套操作步骤。

不提交真实秘密、本地 state、cache、原始 export 或受保护 runtime 文件内容。

## 开始使用

容器使用、已验证的版本 digest 和挂载方式见 [OCI runtime](docs/operations/06-oci-runtime.md)。
从源码运行时，在仓库根目录执行以下命令，并将绝对路径替换为调用方自己的目录：

```bash
uv sync --locked --dev
export ENVIRONMENT_DIR=/absolute/environment
export OUTPUT_DIR=/absolute/output
export GENERATED_DIR="$OUTPUT_DIR/generated"
export PVE_DIR=/absolute/opentofu-root
make generate
make check-generated
```

以上命令生成并检查非敏感派生文件，不操作真实设备。源配置与依赖准备见
[准备与通用约定](docs/operations/00-preparation-and-conventions.md)。开发者整体门禁
`make check` 还要求完整 Ansible 配置和 OpenTofu root；它包含依赖下载，不能当作
容器内的通用环境校验命令。真实环境操作必须从手册的对应章节开始。

## 仓库层次

- `tests/fixtures/environment/` — synthetic offline regression inputs;
  these are not runtime defaults or a prerequisite for external callers.
- `automation/` — reusable Python (`src/iaas_automation`), Ansible, OpenTofu
  modules, Packer, and PVE-node mechanisms.
- `platform/` — documentation-only boundary for handoff to the external
  platform repository; it is not an in-repository platform implementation root
  or compatibility alias.
- `tests/` — repository tests.

Ownership is intentionally split across three repositories:

- IaaS owns PVE/VM lifecycle, K3s node lifecycle and verification, and the
  non-secret handoff bundle.
- The external platform repository owns Flux and shared in-cluster desired
  state such as Cilium, CSI, Gateway, certificates, and observability.
- Application repositories own ordinary application releases, values, and
  application routing resources.

## 调用方源与生成物

以下路径相对于显式选择的 `ENVIRONMENT_DIR`：

| Source | Purpose |
| --- | --- |
| `inventory/pve-cluster.yml` | PVE topology, networks, storage roles, templates, VMID policy, and PCI mappings. |
| `inventory/vms.yml` | VM declarations and lifecycle intent. |
| `inventory/services.yml` | Service metadata. |
| `inventory/foundation.yml` | Foundation recovery metadata. |
| `ansible/` | Environment inventory, group variables, and desired-state variables. |

Generated, reviewable non-secret artifacts are under
`$GENERATED_DIR/{opentofu,ansible,packer,docs}/` (default: `$OUTPUT_DIR/generated/`).
Runtime files use `$OUTPUT_DIR/runtime/`; credentials and state remain caller-owned.
Actual inventories, topology, credentials, state and operational records belong to caller-owned repositories outside this runtime checkout.

## 文档

- [唯一操作手册](docs/operations/README.md)
- [文档索引与架构/历史背景](docs/README.md)
- [可复用自动化实现边界](automation/README.md)
- [通用 OCI runtime 与调用方凭证接口](docs/operations/06-oci-runtime.md)
- [外部 platform repository handoff 边界](platform/README.md)
