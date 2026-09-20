# 本地开发验证

使用项目独立的 `uv` 环境：`uv sync --locked`。运行时镜像继续用 `uv sync --locked --no-dev --group runtime`，Pydantic 是运行依赖，Hypothesis 和 Import Linter 仅属于开发依赖。

- `make test`：完整 pytest 集合，包含本地工具集成测试；不等同于真机验收。
- `make test-fast`：只运行显式 `fast` 标记的五个纯离线测试文件；空选择沿用 pytest 退出码 5。
- `make test-integration`：只运行显式 `integration` 标记的三个本地工具测试文件，使用合成输入和临时目录。
- `make test-opnsense`、`make test-pve`、`make test-k3s`：按 Python 测试文件前缀运行对应模块集合，不隐式执行设备操作。
- `make check-fast`：`test-fast`、类型检查和 import-linter；不替代完整 `make check`。
- `make typecheck`：现有 Python 类型检查。
- `make lint-imports`：检查 common、OPNsense conversion、离线 validation 和 HTTP transport 的依赖方向。
- `make check`：保留完整 CI 检查；需要显式环境 fixture 和 OpenTofu 目录，参数见 CI workflow。

快速集合目前固定为 `test_common_primitives.py`、`test_opnsense_conversion.py`、
`test_opnsense_alias_graph.py`、`test_opnsense_dnat.py` 和 `test_k3s_operations.py`。
本地工具集合目前固定为 `test_import_contracts.py`、`test_pve_make_workflow.py` 和
`tests/ansible/test_opnsense_recovery.py`。新增测试不会因为目录位置自动进入快速集合；
未标记测试仍由 `make test` 和 CI 完整 gate 收集。

这些入口默认串行，不启用 pytest-xdist。性能记录应同时报告所选 marker、完整集合、
运行环境、冷热缓存和省略的检查；没有可比较的隔离收益时不启用并行。

OPNsense 原生数据转换位于 `iaas_automation/opnsense_workflow/conversion/`。公共布尔转换使用 Pydantic 的内置机制；`0`、`"0"`、`False`、`0.0`、`"No"`、`"off"` 等等价，`fasle` 和外围空白输入报错。标准声明继续使用严格准入校验。

转换先解码结构、来源别名及引用，再验证配置字段。普通配置不可表达的对象保留身份和引用，恢复为 `manual_required`；结构、selector、别名冲突和必要引用失败使观察不完整。动态未知字段名在公开 reason 中统一为 `unknown_native_field`，避免把敏感 key 输出到报告。

这些检查使用固定样例、测试替身和临时目录。发布镜像、设备写入及真实客户端验证仍是独立操作。

OPNsense workflow 与 diagnostics 通过 `iaas_automation/http_transport/` 共享一次请求、严格 JSON 解码和响应关闭机制，固定 endpoint 和领域状态映射仍由各自适配器维护。保持单响应 2 MiB、实例累计 8 MiB、默认 `(5, 15)` timeout、现有 TLS 选择和禁止重定向，不自动重试。workflow 的观察 deadline 在请求边界和数据块间检查；这是协作式时间预算，不是可抢占慢流的绝对墙钟保证。HTTP 与流异常由测试替身覆盖。
