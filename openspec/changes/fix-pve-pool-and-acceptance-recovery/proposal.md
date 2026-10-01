# PVE 资源池与模板验收恢复集中修复

## Why

本轮现场发现普通 VM 的 pool 未传入 OpenTofu，模板验收缺完整权限与 helper 预检，明确 guest exec 403 被保留为活动未知，从而阻断已知所属资源清理；容量失败还会被误报为源模板一致性失败。需要交付一个可供调用方继续验收的固定版本，并为 rc.19 的原执行提供正式受控恢复入口。

## What Changes

- 普通 VM 和模板 VM 支持可选 pool；验收临时 VM 必须指定非空既有 pool。池进入请求、计划、审批和执行绑定，克隆时直接入池，启动与清理前核对实际归属；池和 ACL 仍由管理员维护。
- 调用方声明验收专用 VMID 区间，普通 VM 禁用该区间；计划冻结具体 VMID，联网预检和执行复核占用，复用调用方的集群/VMID 互斥，不自动换号或覆盖。
- 增加验收联网 plan，执行前重复完整准入：实际有效 API 权限、池、源身份、节点、存储、网络、总容量及 SSH/helper 条件。离线 check 无凭据、无网络；诊断分类固定且脱敏。
- 区分服务端明确未接受的拒绝与可能已经接受的未知，只解除被证实拒绝的请求不确定性，保留之前写入事实。
- 新增原验收核清及限定清理入口；读取原材料和受信服务端拒绝证据，新授权绑定原执行、冻结清单、新 runtime 和有限截止，保留原材料且不重放原操作。
- 修正源快照缺失诊断，保留首个失败原因；明确 disk_limit_bytes 包括系统盘和 cloud-init/EFI/TPM 等所属附属盘，并在联网 plan 输出总量和必要明细。
- **BREAKING**：直接使用最新请求、记录、计划和结果合同，更新相应消费者、launcher 与节点 helper，不做旧版本兼容、自动转换或迁移。rc.19 原证据仅由受控恢复入口解析，不作为新 start 输入。
- 发布固定 runtime 版本/digest、launcher 校验值及 helper 更新要求，交付软件验证、run-120-1 恢复示例和 infra-ops 适配清单。

## Capabilities

### New Capabilities

- `pve-acceptance-recovery`: 原验收的只读核清、有效新授权下的精确清理及独立真实结果。

### Modified Capabilities

- `pve-automation-foundation`: 普通 VM 实际入池、验收预留区间和环境无关策略。
- `pve-online-preflight`: 有效权限、池与 helper 完整准入和固定分类。
- `pve-template-lifecycle`: 模板 pool 创建、记录及最新发布合同。
- `pve-template-acceptance`: 验收计划、强制 pool、范围/runtime 绑定、拒绝分类及源/容量诊断。
- `runtime-saved-plan-execution`: 普通 VM pool/区间伴随绑定、最新模板记录与调用方 VMID 互斥。
- `runtime-launcher`: 新合同/入口能力、效果和凭据声明，以及固定版本交付。

## Impact

实施仅限 IaaS：inventory/生成、OpenTofu 模块、PVE HTTPS 客户端、发布/验收/恢复合同与执行、能力发现、launcher、受限 snippet helpers、schemas、示例和定向测试。infra-ops 不作代码修改，只交付 [适配清单](infra-ops-adaptation.md)。不建立审批台账、分布式锁服务、签名链、通用恢复框架或逐对象资格系统。

按 A/B 必要正确性和现场已知风险定向修复，软件实施及现有发布流程粗估 M（2–5 天）；现场核清/删除依赖原材料和有效限定授权，单独报告。已有 TLS、绝对截止、pending/消费、所有权和失败关闭保护保留。本站 500–550/551–800 和 cohe/VM798 仅用于示例，不写入通用代码。
