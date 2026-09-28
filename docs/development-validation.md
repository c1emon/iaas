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

OPNsense 原生数据转换位于 `iaas/opnsense_workflow/conversion/`。公共布尔转换使用 Pydantic 的内置机制；`0`、`"0"`、`False`、`0.0`、`"No"`、`"off"` 等等价，`fasle` 和外围空白输入报错。标准声明继续使用严格准入校验。

转换先解码结构、来源别名及引用，再验证配置字段。普通配置不可表达的对象保留身份和引用，恢复为 `manual_required`；结构、selector、别名冲突和必要引用失败使观察不完整。动态未知字段名在公开 reason 中统一为 `unknown_native_field`，避免把敏感 key 输出到报告。

联机 `read` 的 `complete` 只说明枚举完整，验收时还要检查每个对象的 `configuration` / `recovery`。内置 Alias、无可表达地址的网关和空成员组按规格保留为 `manual_required`。原生 Filter 的空 `statetimeout`、DNAT 的空字符串 `address` 与 `%network` 展示字段按资源和字段处理，不把空值兼容扩大到其他类型或未知配置。

这些检查使用固定样例、测试替身和临时目录。发布镜像、设备写入及真实客户端验证仍是独立操作。

OPNsense workflow 与 diagnostics 通过 `iaas/http_transport/` 共享一次请求、严格 JSON 解码和响应关闭机制，固定 endpoint 和领域状态映射仍由各自适配器维护。保持单响应 2 MiB、默认 `(5, 15)` timeout、现有 TLS 选择和禁止重定向，不自动重试。

workflow 的累计 8 MiB 按完整观察计数：一次 `Reader.read` 的全部资源、接口选择、分页和详情共享预算；一次主动检查或关联完成轮询也各有观察预算，嵌套读取不重置计数。下一轮观察（包括失败后的恢复回读）重新计数，避免长流程因复用 reader 耗尽实例预算。独立 diagnostics 仍按其操作实例累计。workflow 的观察 deadline 在请求边界和数据块间检查，换轮字节预算不延长整个 wait 的 deadline；这是协作式时间预算，不是可抢占慢流的绝对墙钟保证。

预算修复使用合成 HTTP 响应验证。恢复后态仅能由新的完整回读确认，仍不可读时保留 `unknown`；独立读取后另建删除候选完成清理不等于原生恢复闭环通过。

`common.errors.Diagnostic` 提供不可变的内部诊断（component、固定 code、可选安全 field_path/status_code）。conversion、HTTP 和 PVE 四类异常附带该属性；安全导出不接收 backend message、payload 或任意 context。现有异常 str/继承/status_code、CLI 前缀和领域 SKIP/FAIL 等状态继续沿用；诊断不会自动加入公共结果 JSON。其他历史错误未批量迁移。

Python 质量检查范围固定在 `pyproject.toml` / `pyrightconfig.json`：Ruff 使用 `E4/E7/E9/F`（不启用 preview、fix 或 formatter），覆盖 common 转换/诊断、OPNsense conversion、HTTP transport 及对应新测试；Pyright 仅对这 9 个核心源码文件使用严格模式，其余项目维持现有模式。runtime dataclass 仍校验未经静态检查的调用，只在对应守卫行保留带理由的局部类型诊断豁免，不对整个模块关闭规则。

## PVE VM private CA

2026-09-27 软件验证覆盖 urllib／proxmoxer 的本地 HTTPS 信任、证书有效期与
SAN 反例、insecure 优先级、公共根保留，以及 CA 随 saved-plan 跨目录恢复、
材料损坏拒绝和 launcher 传输。运行对应 `test_pve_private_ca.py`、
`test_pve_provider_contract.py`、`test_runtime_saved_plans.py` 及输入／调度回归，
launcher 使用 `cd automation/launcher && go test ./...`。

真实 provider 的代表性 TLS 检查命令：

```sh
docker run --rm --entrypoint uv \
  -v "$PWD:/repo:ro" -e PYTHONPATH=/repo/src \
  iaas-runtime:refactor-local run --project /opt/iaas \
  python /repo/tests/integration/provider_private_ca.py
```

实际环境为本地 Linux arm64 runtime 依赖镜像挂载当前源码，OpenTofu 1.12.6、
fixture lock 固定的 bpg/proxmox 0.111.1。无 CA 严格模式拒绝、私有 CA 成功、
后续无 CA 任务仍拒绝、insecure 加无效 CA 成功，四项均通过。
该脚本只访问 loopback HTTPS stub，并允许下载锁定 provider；不访问真实 PVE。
这些结果不代表新镜像已发布，也不代表 infra-ops Runner、现场网络或 PVE 已验收。

### 本机连接真实 PVE（2026-09-28）

macOS arm64，项目 `uv` 环境 Python 3.12.11／OpenSSL 3.0.16，OpenTofu
1.12.6、锁定 bpg/proxmox 0.111.1（Go 1.26.0 构建）。目标使用既有 PVE IP
端点及调用方 CA，凭据经 1Password 临时读取，始终 `insecure: false`。

| 客户端 | 正确 CA | 无 CA | 错误 CA |
| --- | --- | --- | --- |
| urllib | 成功读取 2 个节点 | 按预期拒绝 | 按预期拒绝 |
| proxmoxer | 成功读取 2 个节点 | 按预期拒绝 | 按预期拒绝 |
| macOS 原生 provider | **未通过：certificate is not trusted** | 按预期拒绝 | 按预期拒绝 |

本次共 9 个场景，8 项符合预期；不能记为全部通过。provider 使用当前
`prepare_provider_environment` 生成合并 bundle；其 Go 1.26 在 macOS 的
系统根加载不采用 `SSL_CERT_FILE`，见 [该版本上游实现](https://github.com/golang/go/blob/go1.26.0/src/crypto/x509/cert_pool.go#L96-L111)。
因此不能用此 macOS provider 的失败推断 Linux runtime 的 CA 注入失败。
本地测试阶段已完成；经用户确认，将此项作为已知平台限制记录，不要求
macOS provider 强行通过，也不为此修改系统信任、替换 provider 或扩大平台支持。

实际操作仅为 Python API GET 和 provider 的 nodes data-source-only plan，
`init -backend=false`，未配置远端 backend、保存 state、执行 apply 或修改 VM；
临时 provider 工作目录已清理。未修改系统钥匙串、关闭 TLS 校验或启动 Linux
runtime。后续本机 Docker 的 Linux 验证结果见下节。

### 本机 Docker 连接真实 PVE（2026-09-28）

本机 Colima，Linux arm64，现有 `iaas-runtime:refactor-local` 依赖镜像
（image ID `54c435d310a6`）只读挂载当前源码。Python 3.12.12／OpenSSL
3.0.20，OpenTofu 1.12.6、锁定 bpg/proxmox 0.111.1。连接同一真实 PVE，
凭据在本机经 1Password 读取后仅通过容器 stdin 注入，不写入文件或 Docker
环境配置；保持 `insecure: false`。

| 客户端 | 正确 CA | 无 CA | 错误 CA |
| --- | --- | --- | --- |
| urllib | 成功读取 2 个节点 | 按预期拒绝 | 按预期拒绝 |
| proxmoxer | 成功读取 2 个节点 | 按预期拒绝 | 按预期拒绝 |
| Linux provider | nodes 数据源读取成功 | 按预期拒绝 | 按预期拒绝 |

9/9 场景通过，确认当前 API adapter 与 provider 的任务级 CA 注入在 Linux
上可用于该真实 PVE。provider 仍为 `init -backend=false` 和仅含 nodes 数据源
的 plan，无远端 backend、state 文件、apply 或 VM 变更。测试容器、临时
provider 工作目录、共享脚本和本机临时测试文件均已清理，保留原有基础镜像。

这是本机 Docker 加当前源码的只读验证，不代表新发布镜像、ONE Runner、
VM 创建／删除、跨 Runner saved-plan 执行或业务验收已经通过。
