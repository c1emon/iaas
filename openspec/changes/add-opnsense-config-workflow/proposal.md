# OPNsense 通用配置工作流

当前状态：已获授权，在 `add-opnsense-config-workflow` 实现分支完成 19 项软件实施任务。
验收范围及能力限制见 [acceptance.md](acceptance.md)，任务状态见 [tasks.md](tasks.md)。
尚未合并、发布或执行调用方接入与现场业务验收。

## Why

调用方已有标准资源声明，但日常应用仍需自行编写容器命令、读取 playbook 和增量切片，缺少统一的现场差异、指定候选执行及部分失败结果。需要在现有 launcher/runtime 中补齐通用配置工作流，让调用方保留策略与部署决策，复用 iaas 的资源合同和执行能力。

需求来源：infra-ops 的 `docs/decisions/opnsense-workflow-requirements.md`（2026-09-19 复核修订，IA-01–IA-12）。本 change 自包含 iaas 接受的通用合同；不依赖调用方仓库存在或其目录布局。

## What Changes

- 增加 OPNsense `read / plan / apply / verify` 正式操作，复用环境选择、精确单设备目标、固定运行时、凭据和 local/DinD 传输。
- 仅覆盖既有七类标准资源，支持资源类别和稳定身份选择、有界配置读取、规范化差异、完整候选与实际执行集合分离。
- 应用指定的已审查候选，写前检查相关漂移、引用和共享激活条件；只按已支持的资源依赖排序，不自动加入依赖写入。
- 分开记录保存、激活、配置核对及未知结果；保留写前受影响配置、部分变化和显式有界恢复材料。
- 通过现有 plan/apply 路径准备和执行恢复候选，不提供自动回滚、自动整批重试或任意 API/命令入口。
- 修订现有 NAT、DNAT、接口组规范对 launcher apply 的禁止及未选择资源读取边界；保留直接 Ansible 入口的原有调用方式和离线默认集。

## Capabilities

### New Capabilities

- `opnsense-config-workflow`: 通用资源读取、现场差异、候选执行、验证、部分失败与有界恢复。

### Modified Capabilities

- `runtime-launcher`: 增加 OPNsense 操作及其在线只读/设备写入分类，维持凭据和执行环境隔离。
- `opnsense-nat-management`: 接入显式统一工作流，允许必要的只读引用检查与资源依赖排序，保留 NAT 原生边界和直接入口。
- `opnsense-dnat-management`: 允许正式工作流选择 DNAT，区分执行选择与必要的只读反向引用检查。
- `opnsense-interface-group-management`: 接入统一入口，并区分 reconfigure 请求接受和实际激活结果。

## Impact

- 实施涉及 `automation/launcher/`、`automation/src/iaas_automation/runtime_execution/`、OPNsense 校验/读取适配、`automation/ansible/playbooks/opnsense/`、相关测试和上游通用手册。复用固定 Collection，不在运行时安装依赖，不复制 API 执行器到调用方。
- iaas 只管理标准资源和通用执行结果。策略编译、首次接管决定、业务迁移阶段、部署基线及 `--previous`、所有权元数据和现场业务验收全部由调用方维护；不增加本站配置、策略专用 schema 或默认目标。
- 不包含 SNAT、DHCP、RA、WAN/VLAN、普通路由等新资源、全设备接管、分布式锁、工作流 DSL、跨设备事务、S3 state 或原生 OpenTofu plan 语义。
- 实施分支已按用户授权创建并完成软件验证；未发布、未迁移调用方版本、未访问设备。设计复核历史保留在 review.md，不代表当前实现或现场资格。
