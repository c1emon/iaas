## Context

当前源码 `Acceptance.__init__` 起算 work，`cleanup` 重新起算 cleanup，独立 cleanup `Helper.__init__` 起算 timeout。已有 request 摘要、admission、一次性 caller dispatch、私有 request/journal/result、UPID 和严格所有权检查可以直接复用。SSH 本地超时可能留下远端进程，故仅收紧 launcher timeout 不充分。

本轮是规划；当前运行行为和正式 schemas 不随本 change 改变。GitNexus 索引落后 HEAD 三个提交：Acceptance impact 为 LOW、直接上游为 runtime execution 入口，不能据此证明动态 helper/dispatch 无影响；已直接核对源码。实施前对具体修改符号重跑最新 impact，提交前 detect-changes。

## Decisions

### 1. 当前合同和绑定

两个 request/result kind 保持名称，`schema_version` 升为 2。request 必填 `deadlines: {work_deadline_at, cleanup_deadline_at}`，两值均为固定 UTC 格式 `YYYY-MM-DDTHH:mm:ssZ`（秒精度、真实日历时间；禁止偏移、无时区、分数秒及闰秒）。要求 work <= cleanup；相等允许但不保证补偿时间。运行时 `now >= deadline` 即到期。结构校验允许历史时间以供 observe；只有 start/写入准入要求尚有预算。

保留现有相对 timeout 作为更严格的局部上限，不用于推导或延长批准窗口。阶段进入时允许建立局部 duration 上限，但最终截止总受冻结的绝对时间约束，重试/恢复不重置绝对时间。

这两个入口要求现有 execution-admission/v1 增加同值 `deadlines`，由其操作级校验强制匹配 request；普通操作不增加该必填要求。整个 request（包含 deadlines）进入现有 canonical digest/plan_digest 绑定，execution_id、reservation/pending、target、runtime digest 保持现有一致性检查。独立 deadlines 字段不代替 request 摘要。原 request、完整 admission、journal 以及 result 保留同一 deadlines；observe 核对全部绑定。

能力发现使用 v2 request/result 版本及显式 `absolute_deadlines: true`（两个操作各自声明）。launcher 拒绝能力缺失/合同不匹配，不补默认期限、不把旧相对 timeout 转换成新授权。只交付一个当前合同，不添加 v1 运行兼容分支。

### 2. 时间与调用预算

start 在设施访问/写入前核验两个截止均未到期，并冻结时间材料。每次工作/清理阶段进入和真正发送新写入前再次检查对应窗口。保存 mutation intent 后、发送请求前也须重查；若尚未发送即到期，应记录未发送而不是虚构活动操作。

在同一个 start 时间基准（UTC 与 monotonic 采样对）上，同时将 work、cleanup 两个绝对截止换算为各自的 monotonic 上限；随后阶段只能收紧这两个上限，不得在 cleanup 入口重新换算并扩大预算。使用 UTC 绝对剩余时间和对应 monotonic 剩余预算的较小值，再与现有局部 timeout 上限取最小值。UTC 前跳收紧上限，后跳不能恢复已收紧的预算；不假定时钟异常可恢复授权。无法可信解析/读取时间则拒绝新增写入。设施端与 Runner 需合理同步 UTC；记录这一依赖，不建设时钟同步或漂移认证体系。

HTTP（含库重试）、guest-agent API/固定 guest exec、SSH/helper、UPID 轮询和等待的超时均不得超过对应剩余预算；每次内层重试重算，不给每次重试完整 timeout。禁止库自动重放不确定写入。未正剩余预算不得开始调用。guest 中已发送的 exec、PVE task 和远端 helper 不因本地 timeout 被视为终止。

### 3. 两个入口的阶段归属

accept 的 clone、配置、snippet 上传、启动及 guest 验收受 work 截止约束；所有检查成功或失败后均可进入补偿。work 到期不开始新的上述动作，也不补跑未完成验收。清理所需只读身份/活动/引用检查、stop/delete、VM/卷缺席核验及 snippet 删除受 cleanup 截止约束；只能针对已经证明本次所属且无活动冲突的资源。最终只读 source_unchanged 核清可在 cleanup 窗口内完成，但不能补写 guest 验收或将未完成验收变为通过。

独立 snippet-cleanup 的 start 和原证据/全局范围准入受 work 截止约束；仅在 work 内完成安全准入后进入清理阶段，实际逐文件复核/删除受 cleanup 截止约束。work 到期前未完成准入不能靠 cleanup 窗口首次取得准入。两种 origin 同等执行此规则；清理阶段仍逐次复核实时引用、所有权及互斥，原准入不豁免安全检查。

cleanup 到期停止新设施写入及主动在线轮询，允许本地 journal/result 收集并保留已有响应事实。无清理预算或任务仍活动/未知时不试删、不强行 stop/unlock；保留残留及核清材料。已经发出的请求可以晚于 cutoff 在设施完成；截止是“不得新发起”的边界，不是撤销在途操作或保证资源已清零。

### 4. 远端 helper 必须执行最终检查

helper v2 以明确调用模式决定截止字段要求：模板验收上传模式和 snippet 删除模式必须传入对应绝对 cutoff，缺失、无效或不支持即拒绝写入；普通 VM cloud-init 上传模式保持原有语义，不强制新增截止字段。验收执行必须固定选择验收上传模式，不允许以普通模式重试或降级；不得仅按字段是否存在来决定检查或跳过。helper 在锁等待、引用扫描、摘要核验之后、实际 create/unlink 前重新检查 UTC cutoff；晚到请求不得写入。截止模式的 helper 子调用/锁等待也受剩余预算限制。bootstrap/权限文档同步更新；不使用任意 shell 包装绕过 helper 合同，增加一条普通上传回归验证。

Runner 发起前的检查和 helper 的最终检查都必要。本地杀 SSH 不证明远端终止；丢响应保持 unknown 和活动证据，后续补清理必须先证明原操作已停止。远端时钟偏差是实际限制，软件 fixtures 不构成时钟或真实设施资格证据。

### 5. 结果与恢复

保留 `overall: passed|failed|unknown`；v2 通过冻结 deadlines、结构化 `deadline_outcome: {phase: admission|work|cleanup|null, status: not_exceeded|rejected|exceeded}` 和现有阶段/逐项 reason_code 区分期限与普通失败。固定期限 reason codes 为 `work_deadline_expired`、`cleanup_deadline_expired`，已发送但无法确认仍使用原 unknown/task/helper 原因。多阶段到期以最后阻断阶段为 deadline_outcome，原 work 失败事实保留在 checks/failure_stage/journal，不能被 cleanup 覆盖。

start 到期拒绝是已知事实：记录 `deadline_outcome = {phase: admission, status: rejected}`、具体 cutoff、非零退出码，并在 journal/result 以 `facility_writes: none|issued|unknown` 单独表达本次写入事实；发送首个写入前持久化意图为 unknown，确认已发出后为 issued，确认未发送的期限拒绝为 none。持久化与发送之间崩溃保留 unknown，不能凭意图推断已发出。该字段只描述本次执行，不证明原执行或资源状态。未检查的文件存在性仍为 unknown，整体按既有 unknown 优先规则处理，不强制为 failed、不补造完整库存或清理成功。infra-ops 不得将资源 unknown 直接解释为本次可能已写入，应读取独立写入事实。阶段失败与 deadline 阻断分别记录；cleanup 未完成保留已成功项和 present/unknown 残留；unknown 优先于已知失败，整体不能通过。失败验收即使清理全通过仍非成功；collection 不完整仍非成功。不宣称本地超时意味着取消/回滚。

observe 在原期限过期后仍可读取原材料，无写入、无 operation 凭据、无重新计时、无新副作用；校验历史绑定不以“当前已到期”否定历史事实，不改写原结果。缺材料保持 unknown。

后续补清理使用新 request/admission/execution_id 和当前有效的新 deadlines，保留 retry_of/retry_materials 和原完整资源清单、所有权、摘要、origin/target。重试比较仅允许 timeout、deadlines 及重试关联变化；不修改旧 request/journal/result、不恢复旧窗口，不凭新期限掩盖活动冲突。accept 不增加恢复重跑或 VM/卷补清理新入口。

## Validation and delivery

使用可控制 UTC/monotonic 的定向假 API、helper 文件系统 fixtures 和 launcher 传输测试，覆盖准入到期/相等边界且资源未知与本次零写入分离、阶段迟到、intent 持久化期间到期、工作到期转清理、逐项清理到期、在途任务/丢响应、helper 延迟到达/锁后到期、截止模式缺字段拒绝及普通上传回归、工作期间 UTC 后跳随后进入 cleanup 不扩大 start 冻结预算、observe 历史读取及新授权 retry。核对调用实际 timeout 和零新增写入，复用已有所有权/引用失败测试，不扩大逐对象或真实环境矩阵。

实施后运行范围匹配的 Python/Go、schema 生成一致性、静态检查及严格 OpenSpec 校验。复用 release 流程发布新不可覆盖版本，提供 runtime manifest/platform digest、launcher assets/SHA256SUMS 和 v2 能力输出，实际 release 成功后才标记发布任务。规划、软件验证、发布和真实 PVE 验收分开记录。本轮不执行上述实现或发布任务。
