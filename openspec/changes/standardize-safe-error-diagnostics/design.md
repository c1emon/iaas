## Context

`common.ValidationError` 当前是简单 ValueError 子类；PVE facade 有四类公开异常和 status_code；OPNsense 区分 observation、apply、verify 状态。共同需要的是安全可识别的错误信息，而不是统一所有领域状态。

## Goals / Non-Goals

建立小型、稳定、无输入泄露的错误描述，复用第一/第三阶段的错误边界。不改候选/结果 JSON 格式，不新增日志平台、追踪服务、自动重试或通用 Result 容器，不迁移所有历史错误。

## Decisions

- 在 common/errors 中增加不可变 Diagnostic 值对象：`component`、`code`、可选受控 `field_path`、可选已验证整数 `status_code`。不提供任意 context dict 或任意 message 拼接入口；人类可读文本由已有领域边界从安全模板生成。
- component 与 code 使用首批调用方明确的命名空间，保持枚举/常量集中可追踪，不接受 backend 提供的自由代码。字段路径只接受内部 schema 字段名/记录索引，原生动态 key 不直接透传。
- Diagnostic 的安全导出只包含上列白名单字段，不序列化 exception、cause、input、ctx 或 repr。known-secret 替换可作为附加防护，不能代替不接收原始 payload 的设计。
- 已有 ValidationError 构造、异常继承和 `str` 行为保持；按需增加可选 diagnostic 属性。转换/HTTP 原有 reason 作为命名空间内代码，不新增第二套矛盾分类。PVE 四类异常继续可被原 except 捕获，保留 status_code；facade 在异常捕获时附加固定代码，optional endpoint 的 skip/warn/fail 仍由调用方决定。
- 公共 CLI `FAIL validation:` 前缀、退出码，以及原 OPNsense status/reason 结构不变。无需修改现有候选/恢复 schema；如未来公开 diagnostic 字段，须另做外部合同变更。
- 普通内部数据使用 dataclass 等静态类型，不把所有错误都转成 Pydantic model；Pydantic 继续负责外部输入转换职责。

## Risks / Trade-offs

- 代码过粗或与 domain status 重复 → 只表达失败原因，保留领域状态机与类别；首批涵盖实际调用方，不预建全部错误目录。
- 新增属性影响兼容 → 原 positional message/except/status_code 回归；兼容属性为可选，不强制修改所有 raise。
- 描述字段夹带原生输入 → 建构入口检查有限代码/字段上下文，合成敏感输入验证导出和 CLI 均安全。

## Migration Plan

先增加公共值对象，再接入 conversion 与 HTTP，最后接入 PVE facade；每步保持旧文本/类型合同。前项及本项验收后方进入质量 gate change。撤回不涉及持久格式或设备状态。
