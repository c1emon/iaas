## Context

动机见 proposal.md。当前 `reader.py` 同时承担网络访问、`_provider_row`、`_flatten_provider_row`、`_selected`、标量/列表转换、`normalize_desired` 和观察结果组织。`planning.semantic` 通过 reader 获取比较规范化；网关、接口组、networkgroup 和端口 Alias 的观察也复用这些函数。

此外，网关状态观察还有两条独立布尔路径：`reader._gateway_active_observation` 的 `native_false` 集合和 `gateway_checks._bool`（供 `_configured_monitor`、`_route_check` 使用）。它们不在 `_flatten_provider_row` 的调用链内，但属于本轮迁移范围。

2026-09-20 对 `2ba6d9b` 的 GitNexus 分析：`_flatten_provider_row` 有 7 个直接调用方，深度 3 内影响 12 个符号，风险 CRITICAL。这是图可见范围，不是全部动态调用覆盖证明。实施时须重新分析，并检查测试替身和公开导出兼容。

SDK 评估表明，O-X-L 转换器会过滤内置 Alias、宽松吞掉非法布尔、将任意数字字符串转成整数；独立 SDK 还存在依赖冲突和 DNAT 缺口。本设计保留固定 Collection 的传输/写入角色。

## Goals / Non-Goals

**Goals**

- 以一个独立纯数据 layer 承接七类现有资源的原生形态转换和比较规范化。
- 让 Pydantic 负责已有的类型转换、约束、字段别名和结构校验；仅为设备特殊形态补充可复用 validator。
- 保留身份、引用、不可表达配置、脱敏和恢复边界，减少重复转换分支。

**Non-Goals**

- 不建立全仓库 DTO 框架、插件系统、自动 schema 生成器或配置驱动转换 DSL。
- 不改写 Ansible 参数编码、设备传输、业务授权、完整性判定或全部现有声明验证器。
- 不放宽标准声明的严格布尔要求，不改变候选格式、激活行为或资源范围。

## Decisions

### 1. 通用原语与设备适配分层

建议最小布局（具体文件拆分可在实施中按体量调整）：

```text
iaas_automation/common/conversion.py
    公共标量 TypeAdapter、必要的可复用类型别名、安全 ConversionError
iaas_automation/opnsense_workflow/conversion/
    __init__.py     小型纯函数入口
    types.py        selector、CSV、反向布尔等设备类型
    resources.py    七类资源的模型、字段映射及已知原生字段分类
    normalize.py   标准配置的比较规范化
```

依赖方向为 workflow 调用方 → OPNsense conversion → common/Pydantic。common 不导入设备包；conversion 不导入 reader、transport、executor、planner，不读环境/文件、不持有凭据、不产生网络副作用。

公共原语只实现本轮已有使用者需要的布尔及错误转换，不为未来平台预建抽象。CSV、selector 和原生空值规则具有设备语义，留在 OPNsense 层。备选“所有 helper 放 common”会泄漏设备合同，故不采用。

### 2. 优先采用 Pydantic 内置能力

新增项目运行依赖 `pydantic>=2.13.5,<3`，以 `uv.lock` 固定解析版本及 pydantic-core；本次隔离环境的行为探针使用 2.13.5。实施时验证 Python 3.12 和现有锁定环境，运行时使用既有 locked 安装流程，不现场安装。

- 使用 `BaseModel`、可复用 `Annotated` 类型与缓存的 `TypeAdapter`；不在每条记录上重新构造 adapter。
- `Field(validation_alias=...)`、`AliasChoices` 和 `AliasPath` 处理直接字段映射及嵌套字段路径；多来源须先按来源转换、检查冲突并消费已识别路径，再折叠成单一 canonical 字段。
- 布尔字段使用内置 `bool` schema；需要严格标识/描述的字段使用 `StrictStr`，整数等按具体字段声明约束，不做全局 `isnumeric()` 转换。
- `BeforeValidator` 仅把 selector/CSV 等非标准结构变成可供内置 schema 校验的值；`AfterValidator` 可处理原生来源类型的反向布尔或已定义排序。反转绑定到原生来源，不绑定到同时接收原生和 canonical 值的公共字段。
- `model_validator` 仅承担跨字段别名一致性等纯数据检查。不使用 `PlainValidator` 或 `model_construct` 绕过必要校验，不在 validators 内发起查询。
- 模型聚焦转换所需字段与形态；现有声明验证器继续拥有地址族、资源范围、跨资源规则和写入安全。已迁移的转换不得在 reader 中再保留另一套实现，也不复制两份完整领域 schema。

### 3. 通用布尔转换合同

基础原语直接调用 `TypeAdapter(bool).validate_python`，采用 Pydantic 的确定性转换；JSON 可表达输入的关键行为如下：

| 输入 | 结果 |
| --- | --- |
| `False`、`0`、`0.0`、`"0"` | `False` |
| `"false"`、`"False"`、`"No"`、`"off"`、`"n"`、`"f"`（大小写不敏感） | `False` |
| `True`、`1`、`1.0`、`"1"`、`"true"`、`"YES"`、`"on"`、`"y"`、`"t"` | `True` |
| `"fasle"`、其他拼写、`2`、`-1`、任意容器 | 报错 |
| `None`、`""`、`" false "` | 基础转换报错；不全局 trim 或提供默认值 |

不自建 token 表，也不使用 Python `bool(value)`。`0.0/1.0` 的原生接纳仅适用于设备输入转换，不改变严格声明类型合同。用户已明确 `fasle` 必须报错。

字段特例单独组合在基础类型外：例如接口组 `nogroup=""` 的既有语义是原生 false，校验后反转为 `gui_group=True`；某些已知原生无效标志的空/null 中性值沿用明确的逐字段规则。不得把该规则推广到 `enabled`、未知字段或 selector 的 `selected`。缺失值用字段存在性/`model_fields_set` 区分，不能当成显式 false 或 null。

### 4. 输入与输出边界

提供两个有明确前置条件的纯数据入口：

- `convert_provider_row(resource, row)`：接受原生 API 或已知 Collection 行，返回已成功解码的规范字段、未消费原生字段分类及安全的配置字段错误；普通配置字段失败不能抹去身份/引用所需的可用字段，不决定对象是否可写。
- `normalize_standard_record(resource, record)`：接受两类 canonical 记录——通过 desired 输入准入的声明，或通过 readback 结构/可表达性检查的已观察配置；补充既有比较默认值与规范排序，不重新执行 desired 安全准入，也不把任意原生形态作为合法 desired 输入。现有 deny/reject 规则的读取不需要重新证明创建该规则的权限或安全上下文。

以上是设计接口名，不要求公开结果改为 Pydantic 对象。Pydantic 模型只在 layer 内使用，外部仍返回现有普通字典/列表/布尔/数字/字符串。保留 `normalize_desired` 的必要兼容转发，但让 planning 等内部调用方导入独立转换层，避免通过 reader 获取纯函数。

原生行在转换前保留未修改副本及字段存在信息。转换边界保留额外字段，并按资源分类为已映射配置、已知元数据、已知但不可表达字段、未知字段；禁止默认 `extra='ignore'` 造成静默丢失。未消费字段与 canonical 输出分开保存，不将含未处理 extra 的模型 `model_dump()` 直接作为规范配置，防止同名 extra 覆盖类型转换结果。未知非空配置仍阻止标准配置重建，包含 `0` 和 `False`；空值沿用现有字段策略，不能用 truthiness 判断是否丢弃。元数据白名单按资源限定，不全局删除同名字段。

别名映射前检查同一标准字段的多个来源：分别按来源合同转换，仅反转原生反向来源，语义相同可接受；互相冲突则报错。随后消费全部已识别来源路径，折叠为单一 canonical 值，再进入 canonical 字段模型；已消费来源不能残留在 extra 中。`AliasChoices` 的优先级本身不能代替冲突检查。嵌套来源仅消费对应叶路径，不删除含未知兄弟字段的整个 source/destination 对象。

例如 `disabled="0"` 与 `enabled=True` 各自输入或共同输入都必须导出 `enabled=True`；`disabled="0", enabled="No"` 是冲突。普通同向别名的两种 false 表示共同输入时，输出仍须是布尔 false，不能被 extra 中的字符串覆盖。分组测试 native-only、canonical-only、等价双来源和冲突双来源，并检查属性值与导出值及其类型一致。

### 5. 仅抽象实际重复的特殊形态

- **Selector**：字典使用 key，列表优先显式 key、否则 value；存在但非法的 key 不退回展示文本。所有 selected 标志复用公共布尔转换；缺失/非法标志、重复已选标识、混合非法元素或单选多项选中均拒绝。无选中返回字段声明的空形态，再由字段规则决定有效性。数字样式标识保持字符串，只有明确整数型目标字段才能转换为整数。
- **列表**：原生 CSV/换行、列表、Alias content 映射按字段声明解码；Alias content 是成员键映射，不套 selector 规则。只在既有集合语义字段排序，不擅自去重、拆任意描述字符串或改变顺序敏感字段。
- **字符串与数字**：描述 `"001"`、名称、接口标识保持字符串；sequence 等整数按字段转换，禁止布尔伪装成整数。端口、协议、VIP 地址/前缀组合、URL-table 周期沿用既有规范形式与有效性检查，不让 Pydantic 自动序列化改变外部合同。
- **空值**：缺失、null、空字符串/列表与 false/zero 分开处理。非 URL-table Alias 的空 updatefreq 可按现有规则省略；非空不支持值必须保留为不可表达配置。
- **删除**：`state=absent` 的最小身份声明继续有效，不强制补齐 present 的字段或默认值。readback、desired 比较与恢复均调用相同规范化规则。

### 6. 转换错误不冒充对象缺失

转换分两阶段：先进行行结构、来源冲突和已声明 selector 的解码，再校验配置字段。普通配置字段缺失/非法不使第一阶段的可用字段消失；通过小型分组投影或字段 adapter 保留部分结果，不依赖一次整行 `model_validate` 成功后才提取身份和引用，也不从失败模型中用 `model_construct` 伪造成功值。

内部错误区分 `malformed_shape`、`invalid_value`、`conflicting_sources` 等安全代码，携带受控字段路径，不携带原始值。行结构、selector、来源冲突、身份歧义或必要引用字段解码失败由 reader 映射为 incomplete。已识别对象仅配置字段无法表达时，reader 继续提取已可靠解码的引用，保留 identity、configuration 为 null、recovery 为 manual_required；完整枚举本身仍可 complete。引用与依赖的判断仍由既有逻辑负责；缺失必要引用事实不得被转换成空集合或成功。

代表性回归：规则缺少 `action` 或 `enabled="fasle"`，但身份及指向 `NETS` 的字段有效时，保留该对象和引用、禁止其自动恢复、继续阻止删除 `NETS`，同时不因该对象的配置问题阻断无关对象计划。若异常来自 selector 的 selected 标志，则按 incomplete 处理，不套用普通配置字段的局部失败规则。

Pydantic 模型设置 `hide_input_in_errors=True`；这不能保证 `.errors()` 自动安全。错误边界只提取白名单类型/字段路径，使用 `errors(include_input=False, include_context=False, include_url=False)` 作为中间数据，再限制动态路径段。禁止直接输出 `str(ValidationError)`、原始 input、ctx、API 行或底层异常链。

### 7. 兼容与验证范围

本 change 不重写直接 Ansible 输入准入；标准声明继续拒绝字符串布尔等原合同禁止的值。兼容转换集中在 provider boundary，避免可写输入被意外放宽。

网关 read 与既有可选状态观察的 `monitor_disable`、`monitor_noroute` 使用同一转换入口。reader 用已转换的布尔值决定是否读取已请求检查所需的 monitor route，checker 消费相同 canonical flags；移除独立 `native_false` token 集与 `_bool` 的真假表。缺失/非法值保留 unknown，不得因不匹配 false 集合就报告 not_required/not_applicable。作为本 change 的明确一致化行为，原 `_bool` 接受的外围空白不再隐式 trim，`" false "` 与 `"fasle"` 在此也必须失败；`"off"`、`"f"`、`"n"` 按公共合同接受。不扩展 PF 文本解析或其他网关 schema，也不增加默认运行深度检查的行为。

现有候选/观察/恢复格式、语义默认值、列表排序及原生操作范围保持不变；新模型不得增加字段或导致既有规范输入的摘要漂移。既有 runtime digest 准入继续生效，不承诺旧运行时的候选能跨版本直接 apply。

验证采用公共类型分组测试、七类资源代表样例和既有工作流回归；新增定向覆盖 selector 冲突、未知 false/zero、不可表达对象保留和错误脱敏。无须逐对象现场测试、全设备快照或完整版本矩阵。

## Risks / Trade-offs

- **CRITICAL 调用影响** → 分批替换全部图可见调用方，复用同一转换实现；检查动态调用及旧 helper 残留，不只测试 read。
- **Pydantic 默认忽略额外字段或宽松数值转换** → 明确保留输入额外字段、限制目标字段类型，未知配置按既有合同处理。
- **别名冲突和空值差异** → 冲突前置检查，逐字段声明空值策略；以已有回归冻结输出。
- **标准 schema 和转换模型重复维护** → 本轮只迁移形态与类型转换；业务 validator 保留单一职责，不新增完整镜像 schema 或生成器。
- **新运行依赖及 pydantic-core 打包** → uv 锁定依赖并验证现有运行时安装配置和离线 import；使用现有支持的平台，不额外扩展资格矩阵。

## Bounded property tests and import contracts

按后续授权增加 dev 依赖 Hypothesis、Import Linter，使用 uv 锁定。首批性质只覆盖规范化幂等、输入不被修改、别名等价与冲突、错误脱敏四类；复用有效资源 fixture 构造有界组合，不生成全资源/全版本矩阵，不复制转换实现作为测试 oracle。失败的最小反例纳入普通回归；不输出真实设备样本或凭据。限制样例数，CI 可重放失败；保留现有确定性正反例。

Import Linter 首批检查：common 不导入任何领域包或在线适配器；conversion 不导入 reader/writer/executor/planning/runtime；纯 opnsense_validation 不导入在线工作流适配器。仅约束已存在边界，不重排其他领域依赖。新增 `lint-imports` Make 入口接入 `check`；性质测试由普通 pytest 收集。对导入违规使用临时合成包验证合同本身会失败，不污染仓库源码。

参考：[Hypothesis](https://hypothesis.readthedocs.io/en/latest/quickstart.html)、[Import Linter](https://import-linter.readthedocs.io/en/stable/)。

## Migration Plan

1. 用户审阅设计后，实施前检查工作树并按 AGENTS.md 确认实现分支；本轮不切分支、不 apply。
2. 添加锁定依赖与公共原语；先用 Alias、Filter 建立独立转换入口和代表性回归，再迁移其余五类。
3. 将配置、引用所需字段解码、现有状态观察及比较规范化调用方接入 layer，包括网关 route_required 判定和 gateway_checks 的原生 monitor 标志转换；移除重复转换实现，必要公开入口只留委托。
4. 完成七类离线回归、既有输入准入与工作流/恢复测试、类型检查及依赖安装检查。默认交付到本地源码验证，不以发布镜像测试作为日常反馈循环。
5. 实现若需撤回，以相应源码和依赖变更整体回退；无数据迁移或设备恢复动作。镜像发布和新的设备测试按后续明确请求执行。

## References

- [Pydantic 标准类型与布尔转换](https://docs.pydantic.dev/latest/api/standard_library_types/#booleans)
- [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [字段别名与 AliasPath](https://docs.pydantic.dev/latest/concepts/alias/)
- 本次隔离环境对 Pydantic 2.13.5 的 20 项布尔探针全部符合上表；未改变项目依赖。后续实施以仓库内回归测试接替临时探针。
