## 1. 能力核定

- [x] 1.1 按固定 Collection 和明确目标 OPNsense 版本核定现有只读接口及同步返回，形成按操作分组的支持/缺口说明；验证每个支持结论有源码或官方接口依据，并列出未知/不支持会阻断的操作，不访问设备或增加权限。

## 2. 候选合同与写前准入

- [x] 2.1 实现 v2 候选的保存/配置回读/原生激活合同、警告与 result 缺口记录，阶段规则固定为 `opnsense-provider-response-{resource}-v2`，保留 v1 request；动态 Alias 遵循设备原生缓存刷新，不追加来源、缓存或加载专用证据。
- [x] 2.2 在首写前复核候选绑定、引用完整性、漂移、凭据保护、权限和核心读取上限；核心条件失败时零写入，Alias/Gateway/Group 深度缺口固定 stderr 警告并继续，可选 inspect 不由默认流程调用。
- [x] 2.3 实现 candidate/result/recovery 分立版本及旧恢复材料的受限读取；验证旧候选 apply/verify 明确拒绝、v1 request 仍可用、恢复需已核清后态、不能从旧激活提升结果继承完成证据。

## 3. 原生响应、判定与部分失败

- [x] 3.1 保留原生激活响应与配置回读的默认路径；默认 plan/apply/verify 不调用独立深度 inspect，任何 inspect 读取单独记录，不重复写入、重载或内容刷新。
- [x] 3.2 取消 active=verified 的通用激活提升，实现保存、回读、原生激活与警告/深度结果分离；核心激活失败仍停止依赖阶段，深度观察缺口不阻断默认流程。
- [x] 3.3 保留阶段/资源结果、写前配置和已核清后态，将独立 verify 接到配置回读逻辑；默认成功 scope 为 `saved_configuration`，active 为 `not_attempted`，不追认/改写原 apply 结果；深度 inspect 单独报告。回归冲突停止、部分保存后停止后续写入、不自动重试/回滚，私有输出失败仍保留恢复材料。

## 4. Alias 机制适配

- [x] 4.1 将静态 host/network 的完整成员核对移入可选 inspect；默认只记录保存、回读、原生激活及不可关闭警告，不以成员匹配提升激活。
- [x] 4.2 在可选 inspect 内实现 port Alias 的已加载规则展开检查；验证协议、源/目标端口和范围，以及无消费者时 not_applicable，不创建验证规则。
- [x] 4.3 实现静态 networkgroup 的有效成员计算与活动比较；验证必要现场依赖、未选中期望值不替代现场、动态/不完整依赖不按空集通过，依赖读取不扩大写入。
- [x] 4.4 使动态 Alias 遵循设备原生内容处理和缓存刷新语义；不新增来源、缓存归属/有效期或逐对象加载专用证据，不自行下载/解析/强制刷新；保留保存、回读、原生激活和恢复后态约束。
- [x] 4.5 默认按禁用/删除的配置回读和原生激活结果完成；残留表、空表、缺失或不可读等退役观察由 inspect 可选报告，不清 PF state、不删除未选择对象。

## 5. Gateway 与接口组

- [x] 5.1 默认实现 Gateway 保存、配置回读和原生激活结果；接口/下一跳、必要路由、活动消费者和监控配置移入可选 inspect，不强制默认路由、ping、启用监控或创建消费者。
- [x] 5.2 默认实现接口组保存、配置回读和原生激活结果；可选 inspect 仅报告可读的当前成员和规则接口观察，不表述为注册或 filter reload 完成证明；无消费者不伪造验证。
- [x] 5.3 提供独立 `python -m iaas_automation.opnsense_workflow.inspect --inventory INVENTORY --candidate CANDIDATE --output OUTPUT` 深度核查入口；默认 plan/apply/verify 不调用，inspect 不证明内部子动作或业务验收。

## 6. 集成与交付

- [x] 6.1 运行受影响 workflow/reader/writer/contracts/runtime 的 Python 测试、Ansible 检查及既有 local/DinD 集成测试；验证普通 no-change、activation_recovery、Filter/NAT/VIP 同步确认、恢复及凭据隔离无回归，不新增全版本矩阵。
- [x] 6.2 更新通用手册、合成候选/结果示例、版本迁移说明及软件验证记录；逐项核对 AC-01–AC-10 覆盖，列明已支持与仍阻塞的操作，不将测试替身描述成设备验收。
- [x] 6.3 完成严格 OpenSpec 校验、git diff --check 和提交前 GitNexus 图变更分析；确认 change 的已完成范围与测试一致。分次交付时保留未完成任务，不因记录能力缺口而标记资源实现完成。

实施约束：勾选项仅代表已记录的软件实现与验证；未勾选项仍未完成，详见 [acceptance.md](acceptance.md)。后续 apply 前仍须按仓库规则确认对应实现分支。深度 inspect 是可选后处理，不改变默认 plan/apply/verify 的保存、回读、原生激活语义；SSH、插件、补丁、新权限、发布、调用方接入及真实设备验收均不由本清单自动授权。
