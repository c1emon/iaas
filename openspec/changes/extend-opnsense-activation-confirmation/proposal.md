# OPNsense 激活确认补充能力

状态：按本会话 2026-09-20 修订后的范围分阶段实施；默认保存、配置回读和原生激活成功是工作流主路径，Alias/Gateway/Group 的深度证据缺口记录为不可关闭警告，不阻断默认流程。实际范围见 [acceptance.md](acceptance.md) 和 [tasks.md](tasks.md)。原始需求来源：infra-ops `docs/decisions/opnsense-workflow-requirements.md` §3.1（AC-01–AC-10）；本段修订仅记录本会话确定的范围，不宣称该外部文件已同步。本 change 自包含通用要求，不依赖该仓库或站点目录存在。

## Why

rc.7 已有正式配置工作流，但部分资源保存后缺少深度运行态证据；静态 Alias 的成员匹配还可能将 `accepted`/`unconfirmed` 通用提升为成功，混淆当前状态与本次动作完成。修订后默认流程以保存、配置回读和原生激活返回为完成基础，已知深度证据缺口固定记录为 stderr 警告与 result 字段并继续执行；需要 PF、接口组或运行态深度核查时，使用独立可选 inspect 工具。

## What Changes

- plan 列明保存、配置回读和原生激活条件，以及深度观察缺口；apply 在首个写入前复核整个候选的绑定、漂移、引用和凭据保护条件。Alias/Gateway/Group 的已知深度缺口只产生固定 stderr 警告和 result 记录，不自动阻塞写入。
- 默认采用原生激活响应与配置回读，不在 plan/apply/verify 引入等待；需要深度运行态核查时由独立 inspect 读取并单独报告。
- 取消仅凭成员匹配的通用激活提升，分别报告保存、激活完成、配置回读、内容更新、活动核对和业务验收。
- 独立 verify 按当前状态检查汇总退出码，历史动作未提供和真实不适用项单列；当前检查通过不改写原 apply 结果。
- 将端口 Alias、静态 networkgroup、PBR Gateway、接口组和运行态深度核对移出默认 plan/apply/verify，提供独立可选 inspect 路径；真实 API 不足的范围保留为不可关闭警告与结果缺口。
- 动态 Alias 遵循设备原生缓存刷新语义，不新增来源、缓存归属/有效期或逐对象加载的专用完成证据要求，也不增加独立强制刷新操作。
- 保存成功但深度内容或运行态观察缺失时，默认流程仍记录保存、回读和原生激活结果并继续；配置逆向恢复仍需独立选择、计划和授权，不笼统循环提示重新 plan。
- **BREAKING**：新候选、结果和恢复材料采用工作流格式 v2；旧候选不能在新运行时静默补齐动作后 apply，须重新 plan。request 及 launcher 接口不因本次变更自动升级；具体迁移见 design.md。

## Capabilities

### New Capabilities

无。复用现有正式工作流，不建立并行执行入口。

### Modified Capabilities

- `opnsense-config-workflow`：补充写前确认能力、候选内容动作、可选 inspect，以及操作证据与当前状态分离的结果语义。

## Impact

- 后续实施涉及 `automation/src/iaas_automation/opnsense_workflow/`、固定 Ansible 激活任务、相关 Python/Ansible/runtime 测试和 `docs/operations/02-opnsense.md`。复用固定 Collection、受限读取适配和现有私有结果收集。
- 保留七类资源的字段、引用、显式选择、漂移检查、共享 reload 准入和恢复边界；直接 `manage-*` 入口不自动获得新工作流资格，既有合同不变。
- iaas 负责通用候选/结果、核对器、支持边界与软件测试；调用方负责版本固定、目标授权、串行窗口、环境接入、基线和现场业务验收。
- 本轮不包含设备操作、发布、调用方接入、额外 SSH/插件权限、OPNsense 补丁、任意远程命令、全设备快照、新证据系统、自动回滚或分布式锁。额外通道和真实设备验证另行评估授权。
