# 多 agent 设计复核

日期：2026-09-20。源码基线：`2ba6d9b`。范围为本 change 的 proposal、design、两个 delta spec 和 tasks；未实施转换层、修改项目依赖或操作设备。

三个子 agent 独立检查 Pydantic 机制、代码分层/迁移、规格/验收合同。主 agent 对照源码与测试汇总修订后，由提出问题的子 agent 定向复查。未发现 P1，确认的四项 P2 均已在设计层面关闭。

| 编号 | 发现与具体后果 | 最小修订及验收 | 复查 |
| --- | --- | --- | --- |
| R1 / P2 | `AliasChoices` 后统一反转会把 canonical `enabled=True` 变为 false；未消费的同名 extra 可覆盖 `model_dump()` 中的布尔值 | 按来源转换，仅原生反向来源求反；检查冲突、消费来源叶路径，再折叠 canonical；extra 独立保留。覆盖单来源、等价双来源、冲突与导出类型 | Pydantic 子 agent 确认关闭；design §2/§4、spec 对应场景、task 2.2 |
| R2 / P2 | 一次整行模型校验失败可能丢弃已有身份和引用，将仅配置不可表达的对象误变 incomplete | 结构/selector 解码与配置字段校验分阶段，返回部分可用字段；reader 保留 identity、引用及 manual_required。验证删除保护与无关计划边界 | 合同子 agent 确认关闭；design §4/§6、spec 局部失败场景、task 4.1 |
| R3 / P2 | “已通过标准验证”可能被实现为对 readback 重跑 desired 安全准入，拒绝合法观察到的 block/reject 规则 | 明确规范化接受已做 readback 结构检查或已做 desired 准入的两类 canonical 输入；纯规范化不重新授权 | 架构子 agent 确认关闭；design §4、spec readback 场景、task 4.3 |
| R4 / P2 | reader 网关 route_required 和 gateway_checks._bool 的独立真假表会漏过此次迁移，造成 read 与状态检查对 off/空白处理不一致 | 两条 monitor 标志路径统一接入公共转换；缺失/非法值 unknown，不视作不需要检查；明确取消隐式 trim，加入贯穿两路径的分组回归 | 架构子 agent 确认关闭；design Context/§7、spec gateway 场景、task 4.2 |

## 已执行的验证

- `openspec validate extract-opnsense-pydantic-conversion-layer --strict` 通过；本次三 agent 复核时为 6 条 requirement、21 个 scenario、13 项未实施任务。后续授权增加的性质测试与依赖约束不属于本次复核范围，最新任务以 tasks.md 为准。
- Pydantic 专项在隔离环境使用 2.13.5 核查 19 项合法及 8 项非法布尔表示，并复现 R1 的反转/extra 问题；未改项目依赖。
- 合同专项复用现有 reader 测试，10 passed / 67 deselected，覆盖不可表达对象的身份/引用保留、删除保护、无关对象、无地址网关和空 members。
- 架构专项对 block 规则执行离线探针：readback 校验接受、规范化保留 action、完整 desired 准入拒绝；现有 `test_live_rule_without_recreation_context_is_manual_recovery` 1 passed。
- 源码调用关系通过 GitNexus 核查，设计修订仅落在本 change 目录。临时探针用于验证机制，后续实施仍须把对应回归纳入仓库测试。

## 结论范围

本次确认设计中的四个具体问题已解决，未发现剩余设计阻断。Pydantic 转换层尚未实现；现有测试通过不能替代新实现、运行时打包或设备测试。实施前仍按 AGENTS.md 确认实现分支，不扩大本 change 的默认离线验收范围。
