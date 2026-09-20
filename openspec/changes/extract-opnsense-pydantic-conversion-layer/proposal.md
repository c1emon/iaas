# 提取基于 Pydantic 的 OPNsense 数据转换层

状态：已实施，提交 `aeac3be`；验收范围见本 change 的 `implementation.md`。本 change 未归档，不代表镜像、设备或生产验收。用户已确认 `fasle` 是笔误，必须报错。

2026-09-20 完成三个子 agent 并行复核及修订复查，四项 P2 设计问题已关闭；范围与证据见 [review.md](review.md)。这不代表实现或设备验收已通过。

实施序列第 1 项，无前置 change；完整顺序及边界见 [sequence.md](sequence.md)。用户后续授权增加少量 Hypothesis 性质测试与 Import Linter 分层约束；这部分为复核后的增量，不能沿用原复核结论作为已复核证据。

## Why

OPNsense 原生响应和 Collection 返回值的字段名、布尔值、selector、CSV 与空值形态不同，当前转换散布在 reader 的传输、配置与观察逻辑中，重复规则增加维护成本。引入 Pydantic v2 并独立数据转换层，优先复用库的类型转换，同时保留完整观察、严格写入校验及未知配置边界。

## What Changes

- 提供小型、领域无关的公共标量转换原语，布尔转换直接复用 Pydantic；不维护另一份真假字符串表，不自动纠正拼写。
- 将七类现有 OPNsense 资源的纯数据适配抽到独立 layer，集中管理字段映射、selector、列表形态、字段特例及比较规范化。
- 设备返回值采用声明式兼容转换；调用方的标准声明继续遵守现有严格合同，不把设备兼容规则扩散至写入入口。
- 明确字段缺失、null、空字符串、false/zero、未知字段与元数据的区别；有损或不明确转换不得产生可写配置。
- 保持标准配置、候选及恢复材料的既有外部结构；转换层不访问设备、不决定授权或引用是否成立。
- 添加限定输入空间的规范化性质测试和可执行依赖约束，接入本地与 CI 既有离线入口；测试工具仅加入 dev 依赖。

## Capabilities

### New Capabilities

无。复用现有公共原语与 OPNsense 工作流规格，不新增近似重复的资源能力。

### Modified Capabilities

- `python-common-primitives`: 增加确定性的通用布尔转换及安全失败合同。
- `opnsense-config-workflow`: 增加原生输入转换、字段保真、统一语义输出与异常分类的明确合同。
- `iaas-validation-entrypoints`: 增加有限的性质测试与模块依赖约束检查。

## Impact

- 后续实施涉及 `iaas_automation/common/`、`opnsense_workflow/` 的转换调用方、`pyproject.toml`、`uv.lock`、相关离线测试及必要运行时依赖校验。
- 不引入 O-X-L Python SDK、不修改 vendored Collection，不迁移 PVE 等其他领域，不重写全套资源业务校验。
- 原生布尔输入扩大到 Pydantic 支持的确定性表示（如 `No`、`off`），统一 read 与现有网关可选状态观察的 monitor 标志转换；后者不再单独 trim 非法外围空白。标准声明的类型准入保持不变。字段别名冲突将明确拒绝，避免现有优先级选择掩盖冲突。
- 图分析显示 `_flatten_provider_row` 的上游影响为 **CRITICAL**，涉及配置、引用、状态观察与本地/运行时入口；必须覆盖这些路径的回归。
- 本 change 的默认验收是离线转换与工作流回归，不包含设备写入、镜像发布或生产资格验收。实施前按仓库规则确认实现分支。
