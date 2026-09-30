# PVE 原生执行绝对截止时间

## Why

`pve-template accept` 在实例初始化时重新计算 work timeout，进入 cleanup 时重新计算 cleanup timeout；独立 snippet cleanup 也在启动 helper 时起算。迟到启动、阶段延迟或补执行可能超出 infra-ops 冻结的批准窗口。调用前检查及能力标志不能约束原生阶段或已经启动的远端 helper。

## What Changes

- 两个入口的当前 request/result 合同升级为 v2，必填绝对工作和补偿清理截止时间；绑定规范化 request 摘要、execution admission、执行身份及持久化材料。
- start、各阶段及每次新设施写入执行内部期限检查；API、guest、轮询和 SSH/helper timeout 均受剩余预算限制，远端删除前独立检查截止时间。
- 工作到期只允许限定窗口内的安全清理；清理到期停止新写入，保留已发送操作、残留及未知结果，不宣称取消或回滚。
- observe 只读且不刷新窗口；补清理需新执行、新有效授权和原完整限定清单，不延长旧执行。
- 更新 schema、能力声明、结果原因、共享 fixtures 和定向测试，实施后交付可按 digest/checksum 固定消费的 runtime 和 launcher。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pve-template-acceptance`: 绝对工作/补偿截止、执行绑定及真实结果。
- `pve-snippet-cleanup`: 绝对清理截止、远端写入检查及新授权重试。
- `runtime-launcher`: 当前合同及截止能力检查、文件透传和固定版本交付。

## Impact

预计涉及 acceptance/cleanup contracts、execution admission 的这两个入口校验、原生执行、受限 snippet helpers、能力发现、launcher、schemas/examples 和定向测试。实施预计 M（2–5 天），按 A/B 必要正确性及已知风险定向加固处理。复用已有 journal、原生任务记录及 release 流程，不建审批台账、时间服务、签名链或新证据框架，不影响普通 VM plan/apply 和模板 publication 合同。

infra-ops 负责从合法目标开始时间及批准策略计算并持久化截止时间；IaaS 仅验证绑定并在原生内部落实。真实 PVE、共享环境及生产资格测试需另行限定授权。本轮仅建立并校验 change；不实现、不发布。
