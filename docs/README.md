# 文档索引

从仓库根目录开始；完整操作流程仅见
[《Astra 基础设施操作手册》](operations/README.md)。不要提交秘密、本地 state、
原始 export 或未加密备份。

## 当前操作

- [准备与通用约定](operations/00-preparation-and-conventions.md)
- [交换机](operations/01-switch.md)
- [OPNsense](operations/02-opnsense.md)
- [PVE](operations/03-pve.md)
- [VM Bootstrap](operations/04-vm-bootstrap.md)
- [K3s](operations/05-k3s.md)
- [VM → K3s E2E 测试记录](operations/k3s-bootstrap-e2e-plan.md)
- [全链路验收与恢复](operations/06-acceptance-and-recovery.md)

## 生成参考

以下文件是从环境源生成的非敏感审查参考，不能手工修改或替代操作手册：

- [PVE VMs](../environments/astra/generated/docs/pve-vms.md)
- [Services](../environments/astra/generated/docs/services.md)
- [Foundation recovery](../environments/astra/generated/docs/foundation-recovery.md)

## 架构与历史背景

- [环境架构参考](architecture.md)
- [K3s 平台设计](k3s-foundation-platform-design.md)
- [Forgejo 驱动的 IaaS 与基础平台交付设计及任务清单](decisions/forgejo-iaas-platform-delivery.md)
- [Roadmap and backlog](roadmap.md)
- [PVE automation preflight decision](decisions/pve-automation-preflight.md)
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
- [Review remediation roadmap](review-remediation-roadmap.md)

这些内容用于理解设计、决策和历史证据；如果其中的操作叙述与手册不同，以
`operations/` 中的当前手册为准。

## 当前仓库所有权边界

当前采用三方所有权模型：

- IaaS 仓库负责 PVE/VM 生命周期、K3s 节点生命周期与只读验证，以及交付
  给平台仓库的非秘密 handoff bundle。
- 外部 platform repository 负责 Flux、Cilium、CSI、Gateway、证书、可观测性
  等共享 in-cluster desired state。
- application repositories 负责普通应用发布、应用配置和应用路由资源。

本仓库的 `platform/` 仅记录外部 handoff 边界，不是 platform 实现根，也不
提供兼容别名。平台仓库的传输、签名、CI 触发和消费结果不由本仓库执行或
背书。
