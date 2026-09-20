# 实施记录

前两阶段已提交，在 `implement-iaas-quality-series` 实施。Luna/high 子 agent 编写共享 helper 与测试；主 agent 接入两个适配器并复核。

- 新增 `http_transport`：单次 requests 调用，固定禁止重定向，保留 TLS 与默认 `(5, 15)` timeout，严格 JSON、字节累计和协作式 deadline。失败为固定 reason 与可选 status_code，抑制 backend 异常链。
- workflow 和 diagnostics 保留原 endpoint/credential/session 以及 status/reason 映射。每次请求从实例计数初始化预算，并在 finally 回写累计字节；单响应 2 MiB、累计 8 MiB 不变。
- 修复 workflow 非 2xx 响应关闭缺口，流异常也进入受控错误。requests 的 socket timeout / deadline 检查不声称能够抢占所有慢流。
- 新增第四组 import contract，前三组禁止导入在线 HTTP transport；合成违规验证覆盖新增合同。
- 受影响 adapter/reader/inspect/diagnostics/budget/import 回归 157 passed；helper 首轮 10 passed。类型接口与最终 deadline 修订后，helper/adapter/budget/import 定向集 26 passed；追加 NaN 拒绝用例 1 passed。Pyright 0 errors，四组依赖合同通过，严格 OpenSpec 通过。
- 预编辑图分析：reader._request HIGH，共享 helper CRITICAL，覆盖两类读取调用链；diagnostics.call 为 UNKNOWN，已用实际调用点和回归核对。没有新增写入、重试、SDK、发布或设备验证。
