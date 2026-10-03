# Planning review

## 需求覆盖

| 用户提出的检查点／能力 | 对应规范／任务 |
| --- | --- |
| 镜像、依赖网络传输有限重试，固定版本及 checksum | image-build-tool；4.3–4.4 |
| 上传／导入／完整克隆／模板转换观察同一 UPID | bounded-observation-executor、pve-template-lifecycle；1.3–1.5、2.1 |
| 克隆后的 UUID、资源池、完整卷及 volid/vmid 同步 | pve-template-acceptance；2.2 |
| 修改配置与磁盘容量收敛 | lifecycle、acceptance、pve-execution-results；2.1、2.3、2.6 |
| 启动、QGA、cloud-init，临时查询失败与同 PID | pve-template-acceptance；2.3 |
| 来宾根分区／文件系统、地址／路由／DNS | pve-template-acceptance；2.4 |
| 删除后 VM／磁盘从成功查询的旧清单消失 | acceptance、recovery、lifecycle；2.5 |
| snippet 上传／删除后只读文件及引用核验 | pve-snippet-cleanup；2.7 |
| 统一有限等待与只读重试，不续绝对截止／不重放写操作 | bounded-observation-executor；1.2–1.5 |
| 失败前必要观察证据，阶段／时间／字段／原因 | bounded-observation-executor、pve-execution-results；2.2、3.1–3.2 |
| journal 未登记资源的限定恢复 | pve-acceptance-recovery；3.3–3.5，原 clone marker／UPID／完整候选快照联合证明 |
| 简单 build/test 内存观察：已测不足拒绝，缺数据 unknown 单独不阻断 | image-build-tool；4.1–4.2 |
| 原生停止诊断，完成阶段／活动／归属／残留／恢复能力，failed 与 unknown 独立 | pve-execution-results；3.1–3.2 |
| 普通 post-apply／独立 verify 入口冻结有限只读窗口，不新增审批门禁 | pve-execution-results；1.2、2.6、5.1 |
| 离线 check、当前合同、不支持参数显式错误 | runtime-environment-config；1.2、5.1 |

## 语义边界复核

- 底层已有 bounded HTTP transport 不新增自动重试；组件在已准入的只读 probe 外层复用其单次请求与安全错误分类。
- 本轮没有 runtime 函数修改；实施任务要求实际编辑前的 impact 与提交前 detect-changes。此前代码导航的索引不完整／UNKNOWN 不能作为无影响结论，设计依据已直接核对的运行路径。
- 三种等待用途共用预算／证据机制，各域自行明确 pending；HTTP POST 不自动视为写或读。exec 派发和同 PID 状态查询分开。
- 原生非 OK、权限／TLS 错误、身份／归属冲突不按瞬态重试；缺 exitstatus 不冒充明确失败或成功。外部插件不做补偿。
- 预登记正例需原 preview 绑定并通过原 clone description 传入的 marker、原成功 UPID、门禁前完整候选 UUID／slot→volid，以及当前独立配置／content／pool／source／活动核验。负例包含仅 VMID／marker、缺完整原候选、未知活动和 VMID／卷复用。新批准不能替代所有权或当前活动核验。
- 按阶段／检查／资源分组的必要证据有时间及观察范围，终态失败证据不被后续 cleanup/source 覆盖；候选／owned、存在／未知、failed 检查／unknown 整体分开。消费者不依赖私有日志，公共字段仍按安全 allowlist。
- 软件、固定版本发布、限定真实验收、日常部署分别陈述；当前没有执行实施、发布或设施操作。
- 普通验证组入口以适用 timeout 或内部 120 秒默认值冻结一次窗口，各对象与重试共用，已有明确截止只收紧；不新增 apply admission 必填预算字段。内存仅比较直接已测余量与客体申请量，缺测量报告 unknown，不增全布局资格门禁。

## 验证

`openspec validate add-pve-observation-executor-and-stop-diagnostics --strict` 通过；proposal/design/tasks 和 8 个 capability delta 均已生成。这里只表示规划格式校验及以下复核范围完成，实施任务全部未勾选，不代表软件能力已交付或真实验收通过。

## 多子 agent 初轮复核（2026-10-04）

三个只读复核分别覆盖需求／合同一致性、执行器与现有路径、恢复／诊断／内存安全边界。主 agent 合并后确认没有两轮需求漏项。以下为初轮时尚未修订的问题，位置指初轮版本；修正后的状态见最后的闭环记录。严格格式校验不代替语义复核。

### P1：登记前恢复的正向关联规则未确定

位置：design.md:67–71、specs/pve-acceptance-recovery/spec.md:4、17。

“独立原生创建关联”尚无确定的材料入口、关联字段和接受规则，入口确认留到实施前。原候选 UUID 与当前 UUID 一致不能单独证明属于原克隆，任务成功与当前完整卷视图也不能代替创建关联。不能断言当前原生接口一定没有可行入口，但尚不能据此认定正向恢复设计已可实施。

最低修订：先核实一条当前可取得的原任务／资源关联规则，固定一个可恢复停止点及成功正例；若无法确认，明确设计阻塞和先行只读可行性任务。保留 evidence 不足拒绝的边界，不增加全局审计系统或所有早停点支持。

### P2：普通 PVE verify 的预算来源缺失

位置：specs/pve-execution-results/spec.md:8；现有 src/iaas/runtime_execution/pve_contracts.py:115、plans.py:466、521、pve_results.py 的 verify_configuration。

新规范要求原执行预算，但普通 PVE admission／验证调用尚无可继承的绝对截止绑定或预算参数；基线还支持独立、重复只读 verify。一律使用已过期的原截止会阻断后续读取当前事实。

最低修订：明确执行内 post-apply 收敛的截止来源、冻结、合同绑定和传播；独立 verify 使用自己的有限只读观察窗口，继续绑定原计划／身份，不续原写授权、不修改原结果、不推断历史成功。补原截止已过而独立只读验证仍可执行的场景。

### P2：失败证据的保留范围存在歧义

位置：design.md:52、59、specs/pve-execution-results/spec.md:16。

已有规范要求失败前保存 volid/vmid 和 material changes，不能据此断言实现会丢证据；但“最后必要观察”尚未明确按 phase/check/resource 保存，存在被实现成全执行单槽的歧义。

最低修订：按检查身份保留终止判定证据，后续 cleanup/source 观察不覆盖原 claim 失败字段；补 claim 失败后继续观察，最终诊断仍可消费原两卷及后续事实的场景与任务。

### 其余结论及验证范围

统一只读执行器、同 UPID/PID、单次写派发、显式 transient/pending 分类、非延长截止、外部失败直报、候选／owned 区分、当前活动重查、历史不改写和安全诊断维度均方向一致。cgroup 映射、隐藏祖先处理及执行开销常量可在已列内存任务内确定，不另建容量管理系统。

初轮复核没有更改 proposal/design/spec/tasks，没有实施、发布、凭据读取或设施操作，只追加复核结论；后续修正见下。

## 修正与再次复核闭环（2026-10-04）

| 问题 | 修正 | 再次复核 |
| --- | --- | --- |
| P1 登记前创建关联 | 确定当前 clone description 持久化入口；preview 一用 nonce、原 intent／成功 UPID、门禁前完整候选 UUID／slot→volid 与当前严格核验组成联合证据。缺完整原证据不认领，不另写 marker，不从当前新盘扩 scope。 | 安全子 agent 确认关闭；覆盖子 agent 确认正例、负例与任务一致。 |
| P2 普通 verify 预算 | 普通 apply admission 的 verification_deadline_at 在首次设施派发前绑定／持久化／冻结并传播；独立 verify 用 options.observation_deadline_at 的新只读窗口，不续原写权、不改原结果。 | 执行器子 agent 确认关闭；覆盖子 agent 确认第 9 个 capability 与任务一致。 |
| P2 失败证据保留 | 按 phase/check/resource-or-task 保存终态证据，cleanup/source 不覆盖 claim；增加原两卷失败后继续观察且诊断同时保留各检查证据的场景。 | 覆盖子 agent 确认关闭。 |
| 再次复核新增 P2：VM 已不存在的后续恢复 | present 时重核 marker／UUID／完整挂载；authoritative absent 时只处理此前已在 present 状态独立证明并冻结的范围，绑定必要前次恢复材料、核余项／引用／权限／活动，不重删 VM。无冻结 scope 或替换 VMID 拒绝。 | 安全子 agent 终轮确认关闭；覆盖子 agent 确认符合既有恢复边界。 |

原生参数／持久化路径通过官方文档和公开 qemu-server 源码只读核对，来源在 design.md。这个核对确定了规划的可实现入口，不代表目标设施已验收。三位子 agent 的终轮复核未发现新的实质问题；proposal/design/spec/tasks 与本记录已同步。

本次只修正规划及复核记录，没有 runtime/schema 实施、发布、凭据读取或 PVE 操作；所有实施任务仍未勾选。

## 当前未正式发布阶段的范围复核（2026-10-04）

本轮再次由三个子 agent 从范围／维护成本、观察预算、资源与删除安全边界复核。上轮结论说明修订逻辑自洽；本轮发现两处新增要求超过当前阶段的最小充分方案。以下为当时的范围收减建议，最新修正状态见末尾；这些记录不构成当前新增门禁。

### P2：普通只读验证预算被扩成设施审批门禁

runtime-saved-plan-execution delta:4、16 与 design.md:29–31 新增两个必填绝对截止，其中只读验证截止缺失／到期还会禁止普通 apply。这不是解决观察有界性所必需，也增加了 infra-ops 审批材料接线成本。

建议：普通 post-apply 验证组入口和独立 verify 调用入口，从已有 timeout 或当前版本固定的有限默认值冻结一次 observation cutoff，整个组的对象／probe／重试共享并记录，不逐次重置。若所在操作已有显式绑定绝对截止，仅取更紧值，不续时、不改写。独立 verify 不续原写权或结果。无须为普通只读等待新增必填审批字段，也不因未设置该只读字段新增 apply 拒绝条件。acceptance/recovery/publication 的明确执行窗口及写边界仍按各自合同保持。

### P2：内存预检被扩成全布局资格要求

image-build-tool delta:4、18、design.md:87–89 与 tasks 4.1/4.2 要求 v1/v2 和祖先限制支持，并将所需测量不可得一律变成不能启动。用户要求的是当前执行器的资源检查及明显不足时拒绝，不是所有 cgroup 布局的资格保证。

建议：支持当前实际使用并明确声明的 Linux 执行器布局，检查宿主可用内存、实际容器余量及可见有限祖先；已知不足必须在客体前拒绝。缺失数据、隐藏祖先或非当前布局必须报告 unknown/unsupported 和测量范围，不冒充无限制或充足。核心可用容量不可测与非必要的全祖先完备性应区分，不把任意外围测量盲点变成通用启动禁令；不增加两代兼容矩阵、容器资格认证或资源预留。当前确实无法运行的执行器／KVM 限制保持既有拒绝。

### 文档和任务可压缩

- design.md 的 Migration Plan 实际未包含生产切换、回滚演练或前向兼容，可改名“当前合同更新与验证范围”；不补造迁移流程。
- recovery/lifecycle delta 复制的 rc.19／VM798 专例来自基线，不应成为本次新增历史版本适配／复验承诺；当前 change 使用当前材料正例即可，历史证据与原有防误删规则保持。
- 只推进字段或语义实际变化的合同版本，不能按涉及的 9 个 capability 全部升版；回归针对变化域的代表性软件路径，不把全部镜像重建或真实主线设为每次变更门禁。
- 更新现有接口／调用方说明即可，不新建生产迁移手册。既有条件化的固定版本发布、最多两个顺序临时 VM 的真实验收仍与软件结论分开。

### 必要保留项

共享只读观察组件、写操作单次派发、同 UPID/PID、不续已绑定截止、明确失败直报、逐检查必要证据与敏感字段保护直接对应需求。恢复的原 marker／任务／完整候选身份联合规则、当前活动／权限／引用／精确范围及新的限定批准用于防止误认领和误删，属于必要正确性，不因未正式发布而删减。没有发现需要调度器、审计链、双合同运行或生产切换能力的理由。

此轮初次只追加范围复核记录，没有实施或设施操作；后续用户授权修正记录如下。

## 最新范围修正（2026-10-04）

用户最终选择保留简单内存检查，同时要求去掉普通只读 verify 扩出的 apply 必填审批门禁。当前正文、任务及本报告已同步：

- 内存：仅观察宿主 MemAvailable 和当前容器可直接读到的 limit/usage，与本次 guest memory_mib 比较。已测不足在客体前拒绝；不可读、未知布局或隐藏祖先记录 unknown／原因／scope，单独不阻断。未测量不冒充充足，实际构建成功不补写容量 passed；无全祖先、两代资格矩阵或独立开销策略。既有平台／KVM／磁盘检查和目标 VM 内存配置保留。
- 普通 verify：在 post-apply 验证组入口或独立调用入口，取已有适用的有限 timeout，否则内部默认 120 秒，只冻结一次窗口，全对象／probe／重试共用。已绑定且适用的绝对截止只收紧；不新增普通 execution admission 或独立 verify 的必填 deadline 字段，不因此拒绝有效 apply，不续写权／修改原结果／取消或重跑 provider。
- 删除只为新增普通审批截止而引入的 runtime-saved-plan-execution delta 和 capability；这不修改该既有基线规范。仅推进实际变化的合同版本，回归限于变化域代表性软件路径，Migration Plan 改为“当前合同更新与验证范围”。

执行器与安全子 agent 定向再次复核均确认上述范围问题关闭，未发现新实质问题。严格 OpenSpec 校验通过；本轮只改规划，没有 runtime/schema 实施、发布、凭据读取或 PVE 操作。

## 最终审核（2026-10-04）

需求／合同覆盖、执行器／预算、安全／恢复三个子 agent 完成最终只读审核，均通过；主 agent 汇总未发现新的阻塞或实质问题。

- proposal/design/specs/tasks/README 的当前范围一致：简单内存观察中已测不足拒绝，缺数据单独不阻断且保留 unknown；普通 verify 在入口冻结适用 timeout／内部 120 秒预算，全组共用，没有新增 apply 审批门禁。
- 同任务／PID 观察、单次写派发、非延长截止、状态收敛、失败证据、安全字段和精确归属恢复覆盖原需求；VM 存在／已不存在分支保持独立安全核验，不重放设施操作。
- delta 中 rc.19／VM798 场景和原 legacy 历史例外继承已有基线的受限证据读取边界，不增加本 change 的历史版本适配、旧版 start 或复验任务。当前实施只支持当前运行合同；保留历史证据不等于生产迁移或前向兼容。
- 仅更新实际变化的当前合同，采用变化域的代表性回归；固定版本发布、限定真实验收及 infra-ops 日常部署分别表述，未新增生产切换或资格矩阵。

严格 OpenSpec 校验及本地规划一致性／文件格式检查通过：8 个 capability delta、25 条 requirement、77 个 scenario，31 项实施任务全部未勾选。结论为规范设计可以进入实施阶段，不代表 runtime/schema 已实现、固定镜像已发布或真实设施验收通过。本次审核没有设施操作或凭据读取。
