# 通用运行时架构

本仓库交付可复用的 IaaS 实现和 OCI 镜像。实际环境的拓扑、主机、地址、域名、
账户、部署状态和运行记录由调用方独立维护；本仓库不选择默认环境。

| 所有者 | 输入与职责 | 输出 |
| --- | --- | --- |
| 调用方环境仓库 / CI | YAML inventory、Ansible 数据、OpenTofu root/backend、版本选择、凭据解析与运行授权 | 显式路径、已解析环境变量、受保护文件 |
| IaaS runtime | 校验、生成、PVE/VM 生命周期、K3s 节点操作、支持的网络自动化 | 非敏感生成物、受保护运行材料、检查结果、平台 handoff |
| 外部平台仓库 | 消费 handoff，管理 CNI、CSI、Gateway、证书、GitOps 等集群内期望状态 | 平台部署与运行证据 |

实现位于 `/opt/iaas`。`ENVIRONMENT_DIR` 指向调用方 authored inputs，
`OUTPUT_DIR` 指向可写输出，`GENERATED_DIR` 默认位于其 `generated/` 子目录。
`PVE_DIR` 是调用方单独提供的 OpenTofu working root，需按所选 backend 保持状态。
输入可以只读挂载；敏感运行材料和 state 不属于镜像或非敏感生成物。

凭据仅在调用方解析：可以使用 `op run` / 1Password CI 注入，也可以使用传统
Secret。运行时接收相同的环境变量或受保护文件，不调用 1Password，不拥有其服务账号。

镜像依次构建系统工具、锁定的 Python 与 Ansible 依赖、最后复制本仓库实现。
仅修改仓库实现不要求重新安装依赖。镜像不包含真实环境、测试材料、Git 历史或状态。

仓库测试和离线 CI 使用 `tests/fixtures/environment/` 的合成数据；这些数据只说明
schema 和软件行为，不是部署模板、实际拓扑或环境验收证据。历史 OpenSpec 记录
描述当时的范围；当前使用以 canonical specs 和[操作手册](operations/README.md)为准。

具体挂载、命令、凭据和发布边界见 [OCI runtime](operations/06-oci-runtime.md)。
