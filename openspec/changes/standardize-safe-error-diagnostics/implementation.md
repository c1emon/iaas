# 实施记录

在前三阶段提交后，于 `implement-iaas-quality-series` 实施。主 agent 实现，Luna/high 子 agent 独立编写诊断合同测试。

- common/errors 新增 frozen Diagnostic 与白名单导出；ValidationError 增加可选 diagnostic，保留零个/多个 positional args 的 ValueError 行为。
- ConversionError、HTTP TransportFailure 附加内部诊断；PVE 基类按既有子类生成固定诊断码。两个 PVE facade 的分类/异常捕获无需改写，原 status_code 和消息保持。
- 仅诊断导出接受受控 component/code、静态安全路径和合法 HTTP status；不导出输入、动态 key、后台消息或异常链。不改变公共候选/结果 JSON、CLI 输出或领域状态。
- 预编辑 GitNexus：ValidationError CRITICAL（54 个直接图引用），PveApiError MEDIUM；采取增量属性，require 与既有业务判断不变。
- 定向 common/conversion/HTTP/PVE API/preflight/health：109 passed；新诊断测试：24 passed，含携带诊断时 CLI 精确输出。Pyright 0 errors、四组 import contracts 与严格 OpenSpec 通过。

没有全仓异常迁移、日志系统、重试或设备操作。原消息仅沿用已有边界；安全导出与旧消息是不同接口，不能将原 message 作为 Diagnostic 字段透传。
