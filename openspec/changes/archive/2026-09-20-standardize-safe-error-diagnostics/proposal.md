# 公共安全错误描述

状态：已实施，提交 `88caa66`；验收范围见本 change 的 `implementation.md`。序列第 4 项，前置 `extract-bounded-http-read-transport`。本 change 已于 2026-09-20 归档并同步主规格，不代表镜像、设备或生产验收。

## Why

当前公共验证异常、OPNsense reason 字符串和 PVE API 异常分别提供错误信息。增加小型结构化诊断描述可以让测试和内部调用方按代码处理错误，减少解析消息文本，同时保留各领域的状态与操作员输出。

## What Changes

- 增加领域无关的安全错误描述：组件、稳定代码及受控字段路径；可带明确批准的非敏感数字上下文。
- 首批由转换错误、HTTP 读取失败和 PVE API facade 异常提供描述；不批量重写所有异常。
- 保留原异常继承关系、CLI 前缀/退出码和领域状态，不构建全局成功/失败状态机。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `python-common-primitives`: 增加可供内部调用方读取、可安全序列化的诊断字段合同。
- `pve-api-runtime-adapters`: API 错误附带稳定代码，保留当前异常与检查映射。

## Impact

涉及 common/errors、conversion、http_transport、PVE API errors/client 和定向测试。采用标准库 dataclass/Literal 等即可，不为内部错误额外引入运行时框架或日志服务。
