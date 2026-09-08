# Astra 基础设施操作手册

本目录是 Astra 基础设施的唯一**人工操作权威来源**。按本手册执行从
网络底座到 K3s 集群启动、验证和日常维护的流程；其他 README、设计文档、
OpenSpec 规格和历史记录只说明实现、设计或证据，不能与本手册并列为操作
步骤来源。

这不改变机器可执行事实的所有权：环境 YAML、OpenTofu、Ansible、Packer、
Python 校验器和生成物仍是实际配置与行为的来源。修改任何参数时，先依据本
手册定位源文件，再以相应校验器和生成物确认结果；不得把本手册中的示例当作
可直接替换源文件的独立配置副本。

## 阅读顺序

通用运行镜像的目录、凭证和发布接口见 [OCI runtime](06-oci-runtime.md)。
它是执行方式说明，不替代下列 Astra 基础设施准入与验收步骤。

| 顺序 | 章节 | 完成条件 |
| --- | --- | --- |
| 0 | [准备与通用约定](00-preparation-and-conventions.md) | 控制机、运行时密钥、离线校验和变更记录已就绪。 |
| 1 | [交换机](01-switch.md) | VLAN/端口与到 OPNsense、PVE、基础服务的链路已验证。 |
| 2 | [OPNsense](02-opnsense.md) | 路由、防火墙、VIP、DNS/代理相关路径已按变更边界确认。 |
| 3 | [PVE](03-pve.md) | 模板、bridge、存储、cloud-init 和目标 VM 已创建并通过来宾验收。 |
| 4 | [VM Bootstrap](04-vm-bootstrap.md) | 来宾基线、软件源、信任材料和出站策略已收敛。 |
| 5 | [K3s](05-k3s.md) | K3s 节点意图、安装、集群验证、快照和升级输入已完成。 |
| 6 | [全链路验收与恢复](06-acceptance-and-recovery.md) | 已记录实际证据、已知限制和恢复责任，未把离线测试误报为生产资格。 |

前一章的完成条件是后一章的准入条件。尤其是：PVE 不创建或修改交换机和
OPNsense；`vm_baseline` 不改 VM 网卡、路由或 DNS；K3s 不接管 APT 源、
PVE 生命周期或网络设备配置。

## 当前能力状态标记

各章节使用以下标记，防止把设计、离线验证和真实环境结果混为一谈。

| 标记 | 含义 |
| --- | --- |
| **已实现** | 仓库中有可调用的代码、playbook 或 Make 入口；是否已在 Astra 运行仍需看该次运行证据。 |
| **在线只读** | 会联系真实系统，但不应改变基础设施状态。 |
| **变更操作** | 可能改变设备、主机或集群；必须有明确范围、运行时上下文和变更记录。 |
| **人工/待实现** | 仓库没有自动化实现或环境尚未声明；本手册仅定义准入、交接和不得越界的要求。 |

当前仓库具备 K3s 意图校验、主机 preflight、部署、验证、快照和升级的自动化
基础，但 Astra 尚未提交 K3s 节点组合或环境专用 K3s intent。Cilium、Flux、
TrueNAS CSI、Gateway 和应用工作负载也不是本仓库当前可执行的 K3s 平台
自动化。详情见 [K3s](05-k3s.md) 与
[全链路验收与恢复](06-acceptance-and-recovery.md)。

## 文档与配置的责任边界

| 内容 | 权威位置 | 本手册的职责 |
| --- | --- | --- |
| 交换机、OPNsense、PVE、VM、K3s 的操作步骤 | 本目录 | 唯一操作流程、参数解释、准入和验收标准。 |
| Astra 环境声明 | `environments/astra/inventory/`、`environments/astra/ansible/` | 指出每个字段的含义、编辑顺序和验证方式。 |
| 运行时凭据 | `environments/astra/runtime/*.tpl` 与仓库外受保护文件 | 说明注入方式和文件权限；绝不记录明文。 |
| 生成物 | `environments/astra/generated/` | 说明如何生成、审查和检查新鲜度；不得手工编辑。 |
| 实现机制 | `automation/`、OpenSpec 规格 | 作为开发者参考和合同证据，不重复发布操作流程。 |
| 架构与历史决策 | `docs/architecture.md`、`docs/k3s-foundation-platform-design.md`、`docs/decisions/`、`docs/roadmap.md` | 作为背景；若与本手册冲突，以当前实现和本手册为准，并修正手册后再执行。 |

生成的 `pve-vms.md`、`services.md` 和 `foundation-recovery.md` 是审查用数据
参考，不是替代本手册的第二套操作步骤。
