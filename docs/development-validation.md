# 本地开发验证

使用项目独立的 `uv` 环境：`uv sync --locked`。运行时镜像继续用 `uv sync --locked --no-dev --group runtime`，Pydantic 是运行依赖，Hypothesis 和 Import Linter 仅属于开发依赖。

- `make test`：完整 pytest 集合，包含本地工具集成测试；不等同于真机验收。
- `make typecheck`：现有 Python 类型检查。
- `make lint-imports`：检查 common、OPNsense conversion 和离线 validation 的依赖方向。
- `make check`：保留完整 CI 检查；需要显式环境 fixture 和 OpenTofu 目录，参数见 CI workflow。

OPNsense 原生数据转换位于 `iaas_automation/opnsense_workflow/conversion/`。公共布尔转换使用 Pydantic 的内置机制；`0`、`"0"`、`False`、`0.0`、`"No"`、`"off"` 等等价，`fasle` 和外围空白输入报错。标准声明继续使用严格准入校验。

转换先解码结构、来源别名及引用，再验证配置字段。普通配置不可表达的对象保留身份和引用，恢复为 `manual_required`；结构、selector、别名冲突和必要引用失败使观察不完整。动态未知字段名在公开 reason 中统一为 `unknown_native_field`，避免把敏感 key 输出到报告。

这些检查使用固定样例、测试替身和临时目录。发布镜像、设备写入及真实客户端验证仍是独立操作。
