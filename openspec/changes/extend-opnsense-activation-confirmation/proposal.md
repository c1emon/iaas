# OPNsense 激活确认补充能力

状态：规划，尚未实施。需求来源：infra-ops `docs/decisions/opnsense-workflow-requirements.md` §3.1（2026-09-20 修订，AC-01–AC-10）。本 change 自包含通用要求，不依赖该仓库或站点目录存在。

## Why

rc.7 已有正式配置工作流，但部分资源保存后才发现激活无法确认；静态 Alias 的成员匹配还可能将 `accepted`/`unconfirmed` 通用提升为成功，混淆当前状态与本次动作完成。需要提前识别确认能力缺口，并按资源操作的实际证据判定结果，使调用方能够审查执行范围和处理部分失败。

## What Changes

- plan 列明各实际阶段所需证据及能力缺口，apply 在首个写入前复核整个候选的必要能力；可选活动检查不支持不自动阻塞写入。
- 引入有限时间和次数的只读等待，区分处理中、失败、超时未知和完成；等待不重试写入、重载或内容更新。
- 取消仅凭成员匹配的通用激活提升，分别报告保存、激活完成、配置回读、内容更新、活动核对和业务验收。
- 按不同机制扩展端口 Alias、静态 networkgroup、动态 Alias、禁用/删除、PBR Gateway 和接口组核对；真实 API 不足的操作保持明确缺口，不承诺全部类型可确认。
- 将配置变更派生的内容动作、缓存策略和确认条件纳入候选；不新增独立强制刷新操作，不赋予 `activation_recovery` 强制下载/解析语义。
- **BREAKING**：新候选、结果和恢复材料采用工作流格式 v2；旧候选不能在新运行时静默补齐动作后 apply，须重新 plan。request 及 launcher 接口不因本次变更自动升级；具体迁移见 design.md。

## Capabilities

### New Capabilities

无。复用现有正式工作流，不建立并行执行入口。

### Modified Capabilities

- `opnsense-config-workflow`：补充写前确认能力、候选内容动作、有界等待、各类活动检查，以及操作证据与当前状态分离的结果语义。

## Impact

- 后续实施涉及 `automation/src/iaas_automation/opnsense_workflow/`、固定 Ansible 激活任务、相关 Python/Ansible/runtime 测试和 `docs/operations/02-opnsense.md`。复用固定 Collection、受限读取适配和现有私有结果收集。
- 保留七类资源的字段、引用、显式选择、漂移检查、共享 reload 准入和恢复边界；直接 `manage-*` 入口不自动获得新工作流资格，既有合同不变。
- iaas 负责通用候选/结果、核对器、支持边界与软件测试；调用方负责版本固定、目标授权、串行窗口、环境接入、基线和现场业务验收。
- 本轮不包含设备操作、发布、调用方接入、额外 SSH/插件权限、OPNsense 补丁、任意远程命令、全设备快照、新证据系统、自动回滚或分布式锁。额外通道和真实设备验证另行评估授权。
