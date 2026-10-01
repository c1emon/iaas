# Design

## Context

动机见 [proposal.md](proposal.md)。当前验收 request/result 为 v2，journal 为 v1；验收 admission 绑定请求摘要，缺独立验收 plan，runtime 只记录在 journal/result 中。TemporaryVM 无 pool。普通 inventory 保留 pool，但 OpenTofu protected/unprotected 分支未传递。publication 创建与记录也未绑定池。

验收先检查源配置和总磁盘量，再保存 source_before；故容量失败后没有快照。guest exec 在发请求前记录 intent/活动未知，HTTPS 客户端将 HTTPError 变为普通 OperationFailed，没有明确拒绝的类型和逐请求活动消解。现有独立 snippet cleanup 只能在 VM 删除确认后使用，不能代替本次 VM/磁盘恢复。

GitNexus 当前索引与 HEAD 匹配。Acceptance 的入口引用风险 LOW；TemporaryVM 的影响为 MEDIUM 且为动态调用下界，涉及 acceptance、execution evidence、snippet cleanup、deadline 和 runtime entrypoint。实施仍需对实际编辑符号重新 impact，并以源码、合同和定向测试补足动态边界。

## Goals / Non-Goals

采用一个当前合同，复用现有 canonical digest、preview/admission、journal、执行目录、原生任务记录和 release 流程。原证据解析与新执行合同分开；每条恢复事实都关联原请求，不修改原事实。

不管理池/ACL，不改 infra-ops，不做合同转换、状态迁移、兼容矩阵、通用事件导入器或新的跨 Runner 锁服务；不增加任意 guest 命令、guest SSH、业务验收或源模板修复。

## Decisions

### 1. 当前合同和正式入口

| 对象/入口 | 最新合同与作用 |
| --- | --- |
| publication | publish-request/v2，preview/result/record/v3；cluster_scope必填，可选 pool（省略或 null 表示不入池），preview/record 记录实际池归属 |
| acceptance | request/result/v3；cluster_scope、temporary_vm.pool、vmid_policy.acceptance=[min,max]、runtime.image_digest必填，pool非空 |
| acceptance plan | pve-template plan，options.action=accept，files.acceptance_request；产出 acceptance-preview/v1 |
| acceptance check | pve-template check，options.action=accept；只做当前请求静态校验 |
| acceptance start | pve-template accept，execution_mode=start；消费 acceptance_request、acceptance_preview 和 execution_admission |
| recovery plan | pve-template plan，options.action=recover，files.recovery_request；联网只读核清并产出 acceptance-recovery-preview/v1 |
| recovery start/observe | pve-template recover，execution_mode=start 或 observe；request/result/v1，start 消费 recovery_preview 与新 admission；observe 只读取新恢复执行目录 |

preview 固定 fixed_input、request_digest、runtime、target、必要 preflight/reconciliation 摘要与 evidence references；preview_digest 为除自身摘要字段外规范化内容的 SHA-256。验收和恢复 admission 的 plan_digest 绑定 preview_digest（沿用无 sha256: 前缀格式），并明确携带 request_digest、runtime 和相同 deadlines。新 start 对请求、preview、批准和实际 image digest 做精确匹配。journal 继续使用现有保护/持久化机制，嵌入已校验的完整 preview 快照及其摘要，保留 request/preview/admission/result 摘要关联，使 observe 和当前 snippet acceptance-origin 证据校验能仅凭已绑定原 request/journal 验证新批准；不会把当前网络观察写回旧计划。

验收和恢复使用pve-one-shot-execution-admission/v2，严格列明新增request_digest/runtime/vmid_reservation及恢复关联字段。普通VM与publication沿用现有通用admission格式，在PVE操作准入中要求vmid_reservation扩展；不改变OPNsense/image或standalone snippet的admission版本。原rc.19 admission/v1仅在原证据解析中按原合同校验。

publication、普通 VM 模板消费者及 fixtures 一起使用 record/v3；不自动升级旧记录。普通 OpenTofu native plan、S3 state 和 standalone snippet request/result v2 的语义不作额外版本扩展。snippet 的当前 acceptance-origin 证据校验同步使用新验收合同；恢复自己的 snippet 删除直接复用相同安全检查，不伪造原验收的 vm_delete。

能力声明在现有lifecycle_versions.pve-template中增加publication_request=2、acceptance_preview=1、acceptance_admission/recovery_admission=2、recovery_request/preview/result=1并更新其余对应版本；operation_capabilities.plan用acceptance_plan/recovery_plan布尔能力标识新增action。recover的start/observe在现有execution_modes声明独立效果，不引入新的launcher配置格式或能力转换。

### 2. Pool 和 VMID 策略

普通 VM 的有效 pool 取该 VM 声明，省略/null 表示不入池，不继承模板池或静默使用其他默认池；指定的空白/非法名称拒绝。两条 OpenTofu resource 分支使用 bpg/proxmox 的 pool_id，保持原资源地址与 parity。模板 publication 在原生创建请求中传 pool。池是独立于 VM config 的 PVE 归属事实，须通过权威池/资源查询保存和复核，不假设 config 内有 pool 字段。

cluster.reserved_vm_id_ranges 增加可选 acceptance=[min,max]：声明时与 templates/long_lived/ephemeral_lab 互不重叠，端点包含；普通 VM 不得落入它。验收请求必须携带 acceptance 区间，临时 VMID 必须在内；调用方负责将同一策略传给普通 inventory 和验收计划。普通 plan 在现有 companions 中冻结区间和每个具体 VMID，验收 preview 冻结整个请求。执行时发现调用方送入的池/范围/VMID 与已审材料不同即拒绝，不重分配。

同一集群 VMID 的 reserve/互斥由调用方已有串行化机制持有，覆盖普通 VM、publication、acceptance 和恢复冲突，从准入持续到原生任务及安全清理结束。operation-specific admission 增加 vmid_reservation={cluster_scope, vmids, reservation_id, context_id}，VMID 为当前计划涉及且需要保护的精确集合，两个ID分别匹配现有 consumption.reservation_id 和 serialization.context_id。cluster_scope 是调用方稳定的集群身份，并在请求/计划及批准中绑定到选定 API target；同集群不同节点地址必须映射同一scope。IaaS 验证相应范围的 admission/serialization，复核当前占用，保留 PVE 原生重复 VMID 拒绝；不声称能凭一份 held=true 文件独立证明全局互斥。计划可读占用但不预留/写设施；调用方原子预留拒绝同号并发。

### 3. 完整准入与固定诊断

共享只读准入逻辑用于联网 plan 和写入前复核，实际操作所需的源、池、目标、storage、network、task 和 cleanup 权限按 PVE API 条件式检查，不按角色名推断。查询实际认证主体的有效权限，privilege-separated token 不使用用户单方面 ACL 代替有效权限。合法权限值 0/1（布尔值依现有 API 合同接受）均表示已授予，其值是传播标志；不存在的权限、非法值、查询失败和证据不足分别分类。

克隆的 VM.Clone 检查源；VM.Allocate 按目标 VMID 或目标池的原生 OR 条件检查，不能误设为两者都必需。新 VM 尚不存在时，按平台实际 pool 权限解析语义核对其预计继承权限和直接授权；不能把当前 /vms/newid 上无池继承的查询简单当成未来有效权限，也不能将任意 ACL 做并集。建成后再次查实际目标权限和归属。guest权限表列出ping/get-host-name的VM.GuestAgent.Audit OR VM.GuestAgent.Unrestricted，以及exec/exec-status的VM.GuestAgent.Unrestricted，按原生条件式满足即可，不额外要求两个权限同时独立授予；其他配置/电源/删除、存储、网络和任务读权限按实际端点列明。

VMID 空闲检查需要足以覆盖整个选定集群、该 VMID 的权威可见性。pool-filtered 列表为空不能证明空闲；可复用验收本就必需的受限只读helper完整vmids/节点范围证据，核对与选定API集群/SSH节点的关联，不要求因此扩大全局API权限。API或helper都无法证明时才permission_evidence_insufficient。联网准入还检查模板 UUID/config/volumes、目标节点可用性、storage 类型/可用性/空间、bridge/VLAN 适用权限、CPU/memory/firmware/boot 约束、snippet storage 和 SSH 目标、key/known_hosts、sudo -n 及 helper 必要功能。

upload/delete helpers 增加机器可读的只读能力探测，声明 acceptance create-only、deadline 和删除/reference/digest 检查支持；复用已有受限 helper，无通用 shell 或探测写入。验收必需的 SSH/helper 不能按普通可选 SSH preflight 跳过；检查发生在 clone 前。实际 helper 写边界的截止和所有权门禁仍保留。

只读探测使用helper-capabilities/v1 JSON，分别声明upload的acceptance/create-only/verify/deadline和delete的inspect/exact-delete/reference/digest/deadline能力；继续使用已存在的写边界deadline协议v2，不为本轮另设时间服务或升级普通上传语义。

| reason_code | 含义 |
| --- | --- |
| permission_missing | 权威有效权限对象中缺所需权限 |
| permission_value_invalid | 所需权限存在但值不符合 API 合同 |
| permission_query_failed | 查询传输/API 失败，不能给出权限结论 |
| permission_evidence_insufficient | 查询结构/可见范围不足或未来继承无法可靠判断 |
| pool_required / pool_not_found / pool_membership_mismatch | 请求缺池、权威确认不存在、实际归属不符 |
| helper_unavailable / helper_capability_missing | helper 无法使用或缺必需能力 |
| vmid_out_of_range / vmid_occupied / vmid_reservation_conflict | 区间、当前占用或调用方预留冲突 |
| disk_limit_exceeded / disk_size_unknown / storage_capacity_insufficient | 总上限不足、大小证据不足或存储容量不足 |
| request_rejected / request_outcome_unknown | 已确认未接受/未执行与可能已接受分别处理 |
| source_changed / source_snapshot_missing / source_query_failed / source_evidence_insufficient | 源变化、快照未建立、查询失败、证据不足 |

诊断仅输出分类、阶段、必要对象/操作/缺失权限、必要 HTTP 状态及容量数字；不复制认证头、token、敏感原响应或 guest 输出。首个 failure_stage/reason 不被最后 source recheck 或 cleanup 覆盖。

### 4. 逐请求活动与总写入事实

HTTPS 客户端返回结构化且脱敏的拒绝/传输未知类型。只对可证实在授权/参数等执行前边界拒绝的响应标记 rejected，例如权威 PVE 对该 guest exec 的权限 403；不能把所有 4xx/5xx 或不明中间层响应统判未执行。任务/guest/helper 记录保留方法、限定 endpoint、阶段、status、必要 HTTP code 和证据关联。日志中敏感身份保存在保护材料，公开摘要最小化。

mutation_active 从相关任务/请求是否仍有活动未知计算。明确拒绝只终结该请求；UPID/PID 缺失不是未接受的证明。超时、连接中断、无效/丢失响应和不能确认拒绝来源的错误仍 unknown。guest ping 的明确权限拒绝立即定位失败，不用重复轮询耗尽窗口。

本次 facility_writes 聚合：任何未消解的写入未知则 unknown；否则已有接受/执行的 clone/configure/start/helper 写入则 issued；只有全部确认未发送/未接受且无先前写入才 none。清理许可另行核对活动、授权、池（新执行）、UUID、完整冻结清单和期限，不能仅置一个全局布尔值就删除。

### 5. 原执行核清与新限定清理

recovery-request/v1 固定 target、cluster_scope、runtime、新有限截止、原 caller/native 关联、原 request/journal/可用 result 及 full_original_resources。完整原清单以 journal 为依据，不能缩成剩余项；旧 result 的部分/unknown 资源行是辅助信息，身份或所有权冲突仍拒绝。previous_recoveries 提供已留存关联即可，不要求补齐完整递归历史链。原材料只读，继续校验实际文件摘要、路径边界和核心绑定。

历史日志仅作有限辅助：已有独立 dispatch trace 和可信拒绝导出时可核清；缺失或关联歧义保持 unknown，不补造 trace、不改造 PVE、不要求历史闭环。当前缺权限、VM 停止或无 PID 都不证明历史未执行。preview 显示 administrator_decision；管理员沿用现有的新 execution/request/preview 限定清理批准决定后续处置，不增加批准字段或额外证明材料。

recovery plan 只读核对原请求/执行/消费关联、runtime 原记录、UPID/task 终态、guest 拒绝证据、UUID/配置/磁盘所属及 snippet 上传和引用，产出可审批的 preview。没有最终 result 可在完整绑定 journal 下报告事实；不能补造成功。新 start 必须在新 work 窗口内完成这些复核，随后在新 cleanup 窗口逐项执行；两窗口从新执行同一时间参考冻结，不能刷新原预算。preview 不替代 start 复核。

恢复中的源模板检查用于确认原历史关联，不把源当前可用性/一致性当作独立全克隆资源清理的新增依赖；当前源变化或查询不足单独记录，不改原source_unchanged结论。新验收仍执行完整源身份检查。

rc.19 的 acceptance request/result v2 和 journal v1 按原形读取、校验原 digest/target/admission/deadlines/runtime，并仅用于本恢复操作。它们不进入新 acceptance start，也不改写成新 schema。原 VM798 不受新区间或新 pool 必填要求影响；不为恢复改池。历史材料没有 pool 绑定时，当前 pool 可报告但不是所有权依据，也不添加一个虚构的原 pool。

当前有效清理批准绑定新 recovery execution、preview/request 摘要、原生原 execution、caller 原 pending/消费关系、full_original_resources、新 image digest 和新有限截止；使用新 execution_id 及 recovery_of，保留原 created_by。清理权限仅要求本次核清/停止/删除/参考检查所需权限，已确认拒绝的 guest exec 不需要补齐 guest 执行权才能清理。凭据可轮换，但资源所有权与受保护历史主体关联仍必须验证，凭据值不进入公开身份摘要。

历史 activity/writes unknown 不作为永久清理门禁；确认运行的任务仍阻断。当前 VM 核 UUID、完整盘集、锁和归属；磁盘/snippet 保留精确身份、内容和引用检查。helper 已提供完整全局引用时，不再要求 API 同时看见全部 VM；没有该引用证据时才使用完整 API 视图兜底。不存在的资源不要求无实际用途的删除权限。原生删除丢响应仍停止本次依赖写入；新执行可由管理员另行批准，不从当前 absent 反推历史成功。

新恢复 result 分别记录历史 activity/writes、原验收、本次写入与逐项清理结果。当前完整清单确认 absent、本次写入可判明且收集完整即可 cleanup passed，历史 unknown 不必消解。原结果不改，不授权模板推广。同 ID 仍只 observe；后续清理使用新 preview/批准和完整原清单，不重放旧操作。独立 snippet 清理在确认 VM 删除与当前无引用后，不再要求无关旧 guest/helper 状态全部终结。

### 6. 源与容量诊断

明确源 UUID/config/volume 与已冻结基线不符才 source_changed/failed。初始容量等检查未完成、尚无 source_before 时，最终 source_unchanged 为 unknown/source_snapshot_missing，保留初始 disk_limit_exceeded；不能声称模板变化。查询失败和证据不足分别 unknown，source 不修复。

disk_limit_bytes 是所有要克隆/生成且归属临时 VM 的盘总量，含系统盘、cloud-init、EFI、TPM 等；source/目标尺寸缺失时通过权威 storage content 补证，仍不足则 disk_size_unknown。plan/start 都在 clone 前输出上限、total_required_bytes、slot/volid/size 的必要脱敏明细，并检查目标容量；clone/config 后继续核实际量。示例 40 GiB + 4 MiB = 42,953,867,264 bytes，40 GiB 总上限应拒绝；不自动加余量或改上限。

## Risks / Trade-offs

- 池权限无法提供集群 VMID 完整可见性 → 优先复用既有受限helper的完整只读证据，仍不足则拒绝并由管理员提供所需可见性；不把过滤列表当全集或扩大写权限。
- 计划之后 ACL/容量/归属改变 → start 在写入前复核，运行中写边界保留必要池/UUID/资源/活动检查；plan 是审批材料，不是持续有效性保证。
- 旧 access log 不含请求体或发生重试 → 仅在原意图、主体/路径/时间和串行序列唯一关联时核清；保留未知，不新建日志取证系统。
- 接口合同同时升级影响调用方 → 最终交付适配清单和当前 fixtures，调用方完成接入再验收；不提供双合同运行路径。
- 真实材料或权限不足 → 可以交付软件能力并给出 unknown 恢复报告；VM798 现场清理仍有明确未完成状态，不用 fixtures 宣称已清理。

## Verification and delivery

代表性软件路径和交付任务见 [tasks.md](tasks.md)，调用侧边界见 [infra-ops-adaptation.md](infra-ops-adaptation.md)。复用 pytest、Pyright、OpenTofu 结构/计划 fixture、Go launcher local/DinD 传输 fixtures、现有 helper 本地文件系统测试与 release checks。没有真实设施凭据时不阻断软件规格/发布，但不勾选现场恢复结果。

发布后才填写实际版本/digest、平台 launcher SHA256SUMS、helper 协议/安装要求和经过校验的最终命令。新调用必须使用配套最新 launcher/runtime/helper；无能力拒绝。run-120-1 的操作示例、软件 fixture 结果和实际现场结论分别记录。保留launcher的output新目录规则和basename=execution_id约束；observe使用新的父目录与相同execution_id basename，无需修改该约束。

## Source references

当前端点权限按 [Proxmox QEMU API源代码](https://raw.githubusercontent.com/proxmox/qemu-server/master/src/PVE/API2/Qemu.pm) 与 [Guest Agent API源代码](https://github.com/proxmox/qemu-server/blob/master/src/PVE/API2/Qemu/Agent.pm) 核对；token有效权限按 [Proxmox权限说明](https://raw.githubusercontent.com/proxmox/pve-docs/master/pveum.adoc) 核对，模块pool参数对应 [bpg/proxmox VM资源文档](https://raw.githubusercontent.com/bpg/terraform-provider-proxmox/main/docs/resources/virtual_environment_vm.md) 的pool_id。实施使用现有锁定provider，不因引用上游最新文档而自动升级依赖。
