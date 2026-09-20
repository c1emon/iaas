## Context

现有 pyrightconfig 包含 automation/src、ansible 和 runtime，排除 vendored collections；当前没有 Python lint gate。前四项会建立更小且类型明确的边界，适合作为首批质量检查范围。

## Goals / Non-Goals

检查新增代码中的明显错误及边界类型退化，保留既有检查。不是全仓风格迁移，不启用 formatter 自动写入、不强行消除所有遗留 Any、不增加静态工具重叠矩阵。

## Decisions

- Ruff 通过 uv 加入 dev 并锁定；首批规则采用明确的 `E4/E7/E9/F`，不启用 preview 或 unsafe fixes。门禁只运行 `ruff check`，不运行 `--fix` 或 format。
- 检查范围显式配置为本序列新增的 common 转换/诊断模块、conversion 包、http_transport 包及其新测试。不要依赖 `git diff` 动态决定 CI 范围，避免相同提交因基线不同而通过不同 gate。排除 vendored Collection、生成目录和临时产物。
- Pyright 在相同核心源码路径使用严格模式，保留其余项目的现有模式。对 requests/Pydantic 等外部边界使用小型 Protocol 或有根据的类型注解；不以广泛 ignore/cast 到 Any 让 gate 形式通过。
- `make lint-python` 无环境输入、无网络、无文件修改；加入 check-fast 与完整 check。既有 typecheck 保留，并承载严格路径规则。CI 继续调用仓库入口，不把规则藏在 CI inline 命令里。
- 若引入新 diagnostic 时与旧 errors 文件共存，严格检查范围仅做必要、低成本注解调整；超出已授权模块的广泛改造后置，不通过全仓格式化解决。

## Risks / Trade-offs

- 首批覆盖有限 → 明示文件范围，新增边界纳入配置，后续扩展按改动需要推进。
- 静态规则与外部库动态类型冲突 → 在外部交互边界收敛接口，保留领域代码类型信息；必要局部豁免附具体理由。

## Migration Plan

前置 change 完成后增加工具与配置，修正选定范围实际 lint/type 错误，通过临时合成违规样例检查门禁有效性，再运行既有回归。回退只移除本 gate/依赖及必要注解，不改变行为。

参考：[Ruff linter](https://docs.astral.sh/ruff/linter/)、[Pyright 配置](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)。
