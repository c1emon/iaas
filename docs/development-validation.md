# 本地开发验证

使用项目独立的 `uv` 环境：`uv sync --locked`。运行时镜像继续用 `uv sync --locked --no-dev --group runtime`，Pydantic 是运行依赖，Hypothesis、Import Linter 和 Ruff 仅属于开发依赖。

- `make test`：完整 pytest 集合，包含本地工具集成测试；不等同于真机验收。
- `make test-fast`：只运行显式 `fast` 标记的纯离线测试文件；空选择沿用 pytest 退出码 5。
- `make test-integration`：只运行显式 `integration` 标记的三个本地工具测试文件，使用合成输入和临时目录。
- `make test-opnsense`、`make test-pve`、`make test-k3s`：按 Python 测试文件前缀运行对应模块集合，不隐式执行设备操作。
- `make check-fast`：`test-fast`、类型检查、import-linter 和 Ruff；不替代完整 `make check`。
- `make typecheck`：现有 Python 类型检查。
- `make lint-python`：对本序列新增模块及测试运行 Ruff，不执行自动修复或格式化。
- `make lint-imports`：检查 common、OPNsense conversion、离线 validation 和 HTTP transport 的依赖方向。
- `make check`：保留完整 CI 检查；需要显式环境 fixture 和 OpenTofu 目录，参数见 CI workflow。

快速集合目前固定为 `test_common_primitives.py`、`test_opnsense_conversion.py`、
`test_opnsense_alias_graph.py`、`test_opnsense_dnat.py`、`test_k3s_operations.py`、`test_safe_diagnostics.py`、
`test_http_transport.py` 和 `test_http_read_adapters.py`。
本地工具集合目前固定为 `test_import_contracts.py`、`test_pve_make_workflow.py` 和
`tests/ansible/test_opnsense_recovery.py`。新增测试不会因为目录位置自动进入快速集合；
未标记测试仍由 `make test` 和 CI 完整 gate 收集。

这些入口默认串行，不启用 pytest-xdist。性能记录应同时报告所选 marker、完整集合、
运行环境、冷热缓存和省略的检查；没有可比较的隔离收益时不启用并行。

OPNsense 原生数据转换位于 `iaas_automation/opnsense_workflow/conversion/`。公共布尔转换使用 Pydantic 的内置机制；`0`、`"0"`、`False`、`0.0`、`"No"`、`"off"` 等等价，`fasle` 和外围空白输入报错。标准声明继续使用严格准入校验。

转换先解码结构、来源别名及引用，再验证配置字段。普通配置不可表达的对象保留身份和引用，恢复为 `manual_required`；结构、selector、别名冲突和必要引用失败使观察不完整。动态未知字段名在公开 reason 中统一为 `unknown_native_field`，避免把敏感 key 输出到报告。

联机 `read` 的 `complete` 只说明枚举完整，验收时还要检查每个对象的 `configuration` / `recovery`。内置 Alias、无可表达地址的网关和空成员组按规格保留为 `manual_required`。原生 Filter 的空 `statetimeout`、DNAT 的空字符串 `address` 与 `%network` 展示字段按资源和字段处理，不把空值兼容扩大到其他类型或未知配置。

这些检查使用固定样例、测试替身和临时目录。发布镜像、设备写入及真实客户端验证仍是独立操作。

OPNsense workflow 与 diagnostics 通过 `iaas_automation/http_transport/` 共享一次请求、严格 JSON 解码和响应关闭机制，固定 endpoint 和领域状态映射仍由各自适配器维护。保持单响应 2 MiB、默认 `(5, 15)` timeout、现有 TLS 选择和禁止重定向，不自动重试。

workflow 的累计 8 MiB 按完整观察计数：一次 `Reader.read` 的全部资源、接口选择、分页和详情共享预算；一次主动检查或关联完成轮询也各有观察预算，嵌套读取不重置计数。下一轮观察（包括失败后的恢复回读）重新计数，避免长流程因复用 reader 耗尽实例预算。独立 diagnostics 仍按其操作实例累计。workflow 的观察 deadline 在请求边界和数据块间检查，换轮字节预算不延长整个 wait 的 deadline；这是协作式时间预算，不是可抢占慢流的绝对墙钟保证。

预算修复使用合成 HTTP 响应验证。恢复后态仅能由新的完整回读确认，仍不可读时保留 `unknown`；独立读取后另建删除候选完成清理不等于原生恢复闭环通过。

`common.errors.Diagnostic` 提供不可变的内部诊断（component、固定 code、可选安全 field_path/status_code）。conversion、HTTP 和 PVE 四类异常附带该属性；安全导出不接收 backend message、payload 或任意 context。现有异常 str/继承/status_code、CLI 前缀和领域 SKIP/FAIL 等状态继续沿用；诊断不会自动加入公共结果 JSON。其他历史错误未批量迁移。

Python 质量检查范围固定在 `pyproject.toml` / `pyrightconfig.json`：Ruff 使用 `E4/E7/E9/F`（不启用 preview、fix 或 formatter），覆盖 common 转换/诊断、OPNsense conversion、HTTP transport 及对应新测试；Pyright 仅对这 9 个核心源码文件使用严格模式，其余项目维持现有模式。runtime dataclass 仍校验未经静态检查的调用，只在对应守卫行保留带理由的局部类型诊断豁免，不对整个模块关闭规则。
