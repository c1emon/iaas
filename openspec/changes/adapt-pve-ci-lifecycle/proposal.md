# PVE CI 生命周期与原生执行合同

## Why

现有 PVE 模板构建依赖同步 SSH helper，VM runtime 已支持原生保存计划，但缺少可供调用方可靠登记和核清的对象关联、state 准入、执行身份及配置验证合同。CI 中断、模板同 VMID 重建和凭据更新因此不能只靠现有退出码与文件绑定闭环。

需求依据为 `../infra-ops/docs/operations/pve-ci-iaas-handoff.md`（2026-09-22 审核修订版）。本 change 将其中 IaaS 责任转为自包含合同，不依赖该相邻仓库才能实现或验证。

## What Changes

- 提供独立模板生命周期和 VM 生命周期，公共操作采用 check/read/plan/apply/verify；模板清理也先 plan 后 apply，VM 继续消费原生二进制计划。
- 模板采用受限节点 helper、systemd 托管执行与持久阶段记录，支持断线后只读查询、配置验证和按当前管理归属清理。
- 关联构建或历史观察记录与实际模板对象；需要克隆的计划固定关联，执行前重新核对对象和调用方当前准入结论，拒绝被替换或撤销的模板。
- 扩展保存计划的 API 目标、只读 state 观察与准入、机器审查摘要和固定验证要求，分离固定配置与执行时凭据；核对 provider 实际 SSH 目标的主机信任。
- 分别表达原生执行、副作用、state 持久化、配置核验、来宾就绪及结果收集，保留独立 verify 所需的原执行材料；绑定调用方批准、消费/pending 和互斥交接，但不管理其台账，人工核清不恢复原计划执行资格。
- **BREAKING**：新 PVE 合同拒绝旧计划、旧 helper 和不满足凭据合同的 root；PVE 统一使用 `plan/apply`，移除旧 `prepare-plan/apply-saved-plan` 写入路径及模板 force 替换入口。旧材料保留用于调查，不原地升级或重放。
- 更新本仓库 launcher、模板 helper 安装资产、合成示例、权限文档、发布说明与代表性软件测试。

## Capabilities

### New Capabilities

- `pve-template-lifecycle`: 固定输入预览、可查询远端构建、模板对象关联、历史模板观察和所有权感知的清理。
- `pve-execution-results`: 版本化执行证据、计划关联的配置 verify、只读核清及结果保留。

### Modified Capabilities

- `runtime-launcher`: PVE/模板操作发现、输入隔离、执行身份、非交互认证及中断语义。
- `runtime-saved-plan-execution`: 原生计划审查、实际 API 目标绑定、模板依赖准入、执行时凭据和副作用语义。
- `pve-state-and-secret-operations`: 首次/已有/已核清为空的 state 准入与认证材料分离。
- `pve-online-preflight`: 名称和标记不构成 root/state 所有权或接管授权。
- `pve-automation-foundation`: 复用实际模板构建执行器，禁止原地替换，移除旧 force 合同。

## Non-goals

不实现 infra-ops adapter、Forgejo 工作流、1Password 解析、发布可用清单、S3 部署台账、pending 消费或审批系统；不安装现场 helper、迁移/import/push state、创建现场 VM 或进行实机/业务验收。不扩展宿主机、HA、Ceph、物理网络、K3s 管理，也不建设磁盘 hash 台账、模板 GC、包快照仓库或新的分布式锁。

本轮仅编写并校验 change；实施前按仓库规则确认实现分支。方案按正确性和可维护性选择，不以最少改动或维持旧入口兼容为目标。

## Impact

后续代码涉及 `automation/src/iaas_automation/runtime_execution/`、PVE API/readiness/cloud-init 适配、模板生命周期模块、`automation/launcher/`、PVE 节点 helper/安装资产及相应测试和文档。节点依赖 systemd 和已有镜像处理工具；runtime 沿用已固定 OpenTofu/provider，不新增外部调度服务。其他组件与 OPNsense 的原生候选合同不变；调用方须适配新 PVE 合同，站点上线由调用方另行安排。
