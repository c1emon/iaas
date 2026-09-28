# PVE acceptance / snippet cleanup v1 合同草案

状态：待实现，当前 runtime 尚不支持下列新入口。实现交付时将稳定入口、JSON schema 和共用 JSON fixtures 放到 `docs/contracts/`、`automation/schemas/`、`docs/examples/`，由 capability 声明实际支持的 kind/version；不预先声称某个已发布 runtime 支持。

## 通用规则

- JSON 顶层 `kind` 与整数 `schema_version: 1` 必填，拒绝重复 key、未知版本、无效身份、负数/无穷超时和未声明字段。凭据不得内嵌 request/result。
- request 经现有规范化规则计算 `request_digest`；执行 ID 由 launcher 提供，与 admission 一致。沿用 `execution-admission/v1` 的 approved、consumption reservation、pending 及 serialization 字段，`plan_digest` 绑定该 request digest；不另设审批台账。
- 固定 `target` 含 HTTPS endpoint、节点及现有 TLS 声明；信任材料通过既有 `files.api_ca` 通道提供并随执行材料保留。SSH helper 文件按当前 known_hosts、私钥隔离和跨 Runner 文件传输约定提供。
- 每次副作用前保留私有原始执行记录；公共摘要只展示允许公开的身份、状态、阶段、reason code 和残留。不得输出 cloud-init 内容、期望/实际 hostname 原文、token、私钥或原始 guest 输出。
- 原始材料缺失时保留 `unknown`，不得根据当前对象状态补造历史成功。结果收集失败不能令 caller 结算为通过。

### 首次分派与重复观察

两个新入口均要求显式 `options.execution_mode: start|observe`，不设默认值；该分派选项不改变固定 request 摘要。

| 模式 | 材料与行为 |
| --- | --- |
| `start` | 使用新 execution ID 和完整 admission。调用方必须在既有持久消费记录及互斥内原子确认该执行从未分派，并在调用 runtime 前记为已分派；只准分派一次。运行时先持久化原 request、admission 关联及 journal，再产生副作用；发现已有同 ID 执行材料时拒绝 start。 |
| `observe` | 显式映射 `files.original_execution_dir` 为只读目录，内含原 request、journal 和已有 result（result 可缺失）。核对 operation、execution ID、request digest、target 及 reservation/pending 关联；只观察和收集，不创建、删除或重放 mutation，不重新消费 admission。输入冲突拒绝，目录缺失或核心绑定不完整时返回 unknown/非成功且零写入 PVE。 |

调用方负责跨 Runner 的一次性分派；既有 admission 是声明与绑定材料，IaaS 不查询调用方台账，不能独立将可复制的 admission 文件当作全局一次性令牌。已分派或分派是否发生未知时，只能 observe，原目录丢失也不得改为 start、换 output 或新 reservation 盲目重跑。原任务材料按既有受保护输出机制保留在临时 runtime 外；observe 可输出到新的收集目录，不能覆盖原目录。`pve-template read` 的 journal 查询同样只读。

原目录内引用使用受限相对路径，经现有路径/文件映射校验，禁止逃逸或符号链接。缺 final result 可据 journal 返回部分原始事实，但不能据当前状态合成历史成功。补清理是下面定义的新执行，区别于同 ID 的 observe。

## `pve-template-acceptance-request/v1`

| 字段 | 约束 |
| --- | --- |
| `kind`, `schema_version` | 固定为 `pve-template-acceptance-request`、`1`。 |
| `target` | 固定目标，须与模板记录及准入关联一致；临时 clone 节点可单独指定。 |
| `template_record` | 完整当前 `pve-template-record/v2`，要求 publication 来源、发布 execution/record 引用、artifact digest、UUID、VMID、绑定卷和配置；不接受仅 observation 代替发布记录。 |
| `temporary_vm` | 明确 `node`、空闲 `vmid`、磁盘存储、网络 bridge/VLAN/网络配置、CPU/内存/磁盘上限及声明的启动方式；禁止与源 VMID 相同、无限制默认值或超出资源上限。 |
| `cloud_init` | 固定本次临时 `hostname`，在受保护材料中与执行绑定；不得等于已知模板默认值。必要的网络注入配置由调用方提供。 |
| `required_checks` | v1 必须完整包含 `full_clone`、`disk_boot`、`guest_agent`、`cloud_init`、`injected_hostname`、`source_unchanged`；只能选择支持的固定检查，无任意命令。 |
| `timeouts` | 有界正整数：`work_seconds`、`guest_seconds`、`cleanup_seconds`；guest 期限受剩余工作期限约束，cleanup 有独立预算。 |
| `authorization` | `create_temporary_vm: true`、`delete_temporary_resources: true`，准确约束 temporary_vm 及本次新建附属资源；还需独立的完整 execution admission。 |

入口草案：`iaas run --component pve-template --operation accept`；start 在 environment 中以 `files.acceptance_request` 和 `files.execution_admission` 提供固定材料；observe 按上节提供原目录，不要求新的 admission。沿用 `--execution-id`、`--output`、runtime/environment/engine 参数。只读查询亦可沿用 `pve-template read` 并以原执行 journal 区分操作，不能重放 accept。

## `pve-template-acceptance-result/v1`

必需字段：`kind`、`schema_version`、`execution_id`、`request_digest`、`runtime`、`template`、`temporary_resources`、`checks`、`failure_stage`、`cleanup`、`residuals`、`overall`、`collection`。

- `template` 保留发布 record/execution、artifact、native identity 的关联；`temporary_resources` 记录精确 VM/卷/snippet 身份、创建执行和所有权结论。
- 每项 check 含固定 `id`、`status: passed|failed|unknown|not_attempted`、`reason_code` 及受保护 evidence 引用。`failure_stage` 为首个阻断阶段或 null，后续清理失败另记在 cleanup，不能覆盖最初失败。
- `cleanup` 独立列出 VM、卷、专属 snippet 的状态及 reason；不存在本次专属 snippet 为 `not_required`，已创建资源只有确认删除/已不存在才能收尾通过。
- `residuals` 列出已知存在及存在性未知的精确对象，各含 `existence: present|unknown`、归属结论和保留原因；范围完整性未知时额外标记 `inventory_complete: false`，不能用空数组暗示无残留。
- `overall: unknown`：任何影响结论的活动任务、归属、必需检查、清理/源模板观察或结果收集未知；即使已有确定失败也保留失败分项。
- `overall: failed`：上述事实均可判定，但存在检查失败/已知超时、源模板变更或清理失败/已知残留。
- `overall: passed`：必需检查全通过、所有本次临时资源清理已核对、源模板核验通过且结果已完整收集；业务可用性、外网和 available 推广不包含在该结论内。

## `pve-snippet-cleanup-request/v1`

| 字段 | 约束 |
| --- | --- |
| `kind`, `schema_version` | 固定为 `pve-snippet-cleanup-request`、`1`。 |
| `origin` | `deployment` 或 `acceptance`，必须由原材料证实，不能用切换分支绕过证据要求。 |
| `target` | 原 PVE 目标；相关共享存储范围由运行时完整核实，不由调用方任意缩小。 |
| `original_vm` | 原 node、VMID、native identity。VMID 已被新对象占用时拒绝删除。 |
| `original_execution_id` | origin 对应的原 deployment 或 acceptance execution ID。 |
| `delete_plan` | deployment 必须提供原已批准计划 ID/digest 及执行关联；acceptance 必须为 null。只能用于关联，不能再运行 plan/apply。 |
| `acceptance_evidence` | deployment 必须为 null；acceptance 必须含原验收 request、journal 的受保护文件引用、request digest 及已有 result 引用（result 可为 null），证明原临时 VM、创建/删除授权和本次专属 snippet 清单。 |
| `deletion_evidence` | 两种 origin 均需原删除 execution、native task/结果及 VM 删除确认，不能只给 `true`。deployment 另需 state 写回关联，含 backend/root/workspace 和适用 lineage/serial；acceptance 以原 journal 中确认完成的临时 VM 删除证据关联，不要求或伪造 OpenTofu plan/state。 |
| `ownership_records` | 原生成 manifest、上传记录与 original_execution_id 关联的受保护文件引用及既有摘要。deployment 复用 manifest＋保存计划＋pve-result 的关联；acceptance 复用原验收 journal 中的生成/上传记录。记录不充分则拒绝，不补造历史所有权或另建证据系统。 |
| `snippets` | 明确且去重的有限列表；每项含 `node`、`storage`、`file_id`、`file_name`、`sha256` 及原记录条目引用。必须匹配原记录及原 VM。禁止通配符、路径、仅按前缀发现文件。 |
| `timeout_seconds` | 有界正整数；超时不等于文件未删除。 |
| `retry_of` | 必填，首次独立 cleanup 为 null；补执行为前一次 cleanup execution ID，不能等于本次 ID。acceptance 后首次独立清理仍为 null，以 origin/original_execution_id 关联验收。 |
| `retry_materials` | retry_of 为 null 时必须为 null；否则必须含前次 cleanup 的 request、journal 及已有 result 引用（result 可为 null），绑定 execution ID、request digest 和原清单。 |

入口草案：`iaas run --component pve --operation snippet-cleanup`；start 在 environment 中提供 `files.snippet_cleanup_request`、原关联材料和新 `files.execution_admission`；observe 按通用规则提供原目录。request 中所有证据引用均为 `files.cleanup_evidence_dir` 只读目录内的受限相对路径，使用现有文件映射机制传输，拒绝缺失核心材料、路径逃逸及符号链接。该操作不要求 S3 凭据、不初始化 backend，也不修改已保存 state 材料。

补执行使用新的 cleanup execution ID/admission；加载 retry_materials 后核对 retry_of、前次 request digest、origin、target、original_vm/original_execution_id、原删除/授权/所有权材料及完整 snippets 清单。比较加载后的材料及既有摘要，不把 Runner 挂载路径当资源身份。只允许更新本次超时预算和补执行关联，不能切换 origin、增加/替换文件或换摘要。缺前次 final result 可用完整绑定的 journal，但原 mutation 未确认终止或核心材料缺失时禁止补清理写入。逐项重新检查，原已删除项可返回 already_absent；原结果不可改写。同 ID 重复调用只能 observe。

acceptance 分支仅用于原验收 VM 已确认删除后剩余的专属 snippet。它与 deployment 分支共用归属、完整引用、摘要、互斥和删除后核验，不放宽安全条件，不克隆或再次删除 VM。清理结果独立关联原验收，不回写原 acceptance 的 overall；仍有 VM/卷残留或未知任务时不得把 snippet 清理成功表述为验收通过。

## `pve-snippet-cleanup-result/v1`

必需字段：`kind`、`schema_version`、`execution_id`、`request_digest`、`runtime`、`origin`、`original_vm`、`original_execution_id`、`delete_plan_digest`、`acceptance_request_digest`、`deletion_execution_id`、`retry_of`、`scope_check`、`items`、`residuals`、`overall`、`collection`。deployment 的 delete_plan_digest 必填非空且 acceptance_request_digest 为 null；acceptance 则相反。retry_of 与 request 一致。

每个输入文件必须有一个结果，包含精确身份、`status`、`reason_code`。无权限公开的引用对象详情只存私有证据。

| status | 含义 |
| --- | --- |
| `deleted` | 本次删除已确认完成，并复核文件缺席。 |
| `already_absent` | 原记录及目标有效，完整查询确认原文件已缺席；不伪造历史删除动作。 |
| `referenced` | 仍被 VM/模板相关配置引用，保留。 |
| `mismatch` | 内容摘要或所有权/身份不匹配，保留。 |
| `failed` | 可判定的检查或删除失败；reason 区分权限、范围检查失败和删除失败。 |
| `unknown` | 检查不完整、响应丢失或最终存在性无法判定，保留待查。 |

`scope_check` 报告节点/共享存储范围、权限及查询完整性，不能以“返回 0 个对象”单独证明无引用。`overall` 仅所有文件为 deleted/already_absent 且结果收集完成时 passed；有未知则 unknown，其余未完成为 failed。`residuals` 保留未清理/未知项，部分完成不能报告整批通过。

## 共用软件验收用例

实现时交付 machine-readable fixtures 与期望状态，由 IaaS 测试加载，供 infra-ops 复用；以下是用例范围，不是已执行测试结果。

| 用例 | 必须断言 |
| --- | --- |
| 验收成功 | full clone、启动、全部只读检查、清理和源核验通过；overall passed。 |
| guest 失败/超时 | 原失败阶段保留，已知归属且原操作已终止的临时资源仍清理。 |
| clone/start/delete 响应未知 | 不重放；活动/归属不明的对象保留，overall unknown。 |
| 清理失败 | guest passed 不掩盖残留；overall failed 或 unknown。 |
| 相同/冲突重复调用 | 调用方已分派后跨 Runner 只能 observe；同 ID 同输入不再创建，不同输入拒绝，原目录缺失/摘要不符时零 PVE 写入；首次 start 记录先于副作用。 |
| 已占 VMID、模板替换、注入未生效 | 阻断相应阶段，不能以名字/已有 hostname 代替身份及注入证据。 |
| snippet 删除/缺席 | 返回 deleted/already_absent，并证明没有 VM 删除或 state 写入调用。 |
| 共享存储引用 | 另一节点 VM/模板、相关 pending/snapshot 引用阻断删除。 |
| 摘要/归属错误 | 返回 mismatch，不触发删除。 |
| 权限不足/范围不全 | 不认定无引用，不删除；分别报告确定失败或未知。 |
| 部分失败与补执行 | 首次 retry_of/retry_materials 为 null；合法补执行可通过 schema，重新检查原清单；拒绝自引用、错误原执行、缺核心材料、活动未知、新增条目及新摘要。 |
| 验收遗留 snippet | 临时 VM 删除已确认后可用 acceptance 证据分支单独清理，无需 plan/state；原 VM 身份/授权不符或删除未知则拒绝，不产生 clone/VM delete/state 调用。 |

版本说明同时列出新 kind/version、两个入口、helper 最小版本和安装/权限变化。launcher 接口仍使用当前 v1，旧 runtime 不广告新能力并应拒绝未知操作；不建设历史数据迁移或兼容矩阵。
