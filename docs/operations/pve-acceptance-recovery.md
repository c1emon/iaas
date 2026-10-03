# PVE 原验收受控恢复

恢复先联网只读核清，再使用新的限定清理批准。它不重放原 clone、configure、start
或 guest exec，不修改原 request/journal/result，也不把清理成功改写为验收通过。
软件样例与测试覆盖的是 fake API/helper；现场结论及历史材料定位见[验收材料入口](pve-lifecycle-acceptance.md)。`run-120-1` 是历史实例，每次新处置仍需独立的新批准与当前条件核对。历史403日志仅为辅助材料，不要求为旧执行重建 trace 或改造 PVE。

## 输入及文件映射

当前合同为 recovery request v1、preview/result v2，start 使用共享 one-shot admission v2。
[schema](../../automation/schemas/pve-acceptance-recovery/v1/README.md) 与
[完整脱敏样例](../examples/recovery/README.md) 可供 IaaS/infra-ops 共用校验。
样例中的未来截止、摘要及成功结果都是软件 fixture，不是可直接消费的设施批准。

| files alias | plan/start | observe |
| --- | --- | --- |
| `recovery_request` | 本次固定请求：新 runtime/截止、原关联、完整资源、可信来源声明。 | 可省略；若提供须等于该恢复执行的原请求。 |
| `recovery_preview` | start 必须为实际只读 plan 产物。 | 不读取外部新 preview。 |
| `execution_admission` | start 必须为当前批准的 v2 材料。 | 不加载新的批准。 |
| `original_execution_dir` | 只读原验收目录；request/journal/available result 引用相对该目录。 | 只读本次已派发恢复的 `work/pve-recovery/` 目录。 |
| `cleanup_evidence_dir` | 只读 caller 关联、拒绝证据及 previous recoveries 目录。 | 不需要。 |
| `ssh_key`, `known_hosts` | 隔离的非 root helper SSH 通道；目标来自原请求 `cloud_init.ssh`。 | 不需要。 |
| `api_ca` | 私有 CA 时显式映射；HTTPS 保持校验。 | 不需要。 |

目录与文件不能互为符号链接、越界或与新输出目录重叠；EvidenceRef 的 SHA256
绑定原文件字节。canonical request/preview digest 与文件 SHA256 是不同用途，不能
先重新格式化原文件再更新其摘要。没有最终原 result 时，只能在完整 journal/关联
下保留 unknown 验收结论，不能从现存 VM 补造历史成功。

原 rc.19 acceptance request/result v2、journal v1 仅在 recover 中按原形读取。
当前 acceptance request v3/result v4 也可作为原材料恢复，必须保持原 preview/v2 admission、
runtime、cluster/pool/VMID policy、源模板与结果摘要绑定。不能把当前材料降成 v2 或
重新生成旧 request/journal；恢复成功不改变原验收失败/未知结论。
VM798 不受新验收 VMID 区间阻挡；原材料没有 pool 时不会补出一个历史池绑定。
若原来有 pool，保持原绑定并核当前归属；恢复永不修改池或 ACL。

## run-120-1 正式入口

原 native execution 为 `01591395-b75d-4108-a19d-7e5ccdb99acc-accept`，原 caller
execution 为 `01591395-b75d-4108-a19d-7e5ccdb99acc`，plan 为 `run-120-1`，源为
`cohe/9004`，原临时 VM 为 `cohe/798`。原 UUID、两盘 volid、snippet file_id/digest、
pending/consumption 关联与截止必须取自受保护原材料，不能采用本仓库的合成值。

先在调用方目录准备三个 environment，结构见 `environment-plan.yml`、
`environment-start.yml`、`environment-observe.yml`。把 sample 路径替换成真实只读
材料与隔离 SSH 文件；将 start 的 preview 路径设为下面实际 plan 的输出，将
admission 路径设为本次新批准。`runtime.json` 和请求 `runtime.image_digest` 必须
使用同一已发布固定 digest，launcher 使用该 release 的资产并校验 SHA256SUMS。
实际版本与 digest 以完成发布的产物为准，这里不预填或推测。

以下命令只表达入口；只有实际材料及批准就绪后才能使用：

```sh
RECOVERY_INPUT_DIR=/protected/run-120-1-recovery
RECOVERY_ID=run-120-1-recovery-01

iaas run --runtime-config "$RECOVERY_INPUT_DIR/runtime.json" \
  --environment "$RECOVERY_INPUT_DIR/environment-plan.yml" \
  --engine local --component pve-template --operation plan --scope cohe \
  --output ./recovery-plan-01
```

plan 联网使用 GET 和只读 helper 检查，不消费批准、不创建/启动/删除设施对象。
审查 `recovery-plan-01/plan/recovery-preview.json` 的逐请求 activity、原 issued/unknown
写入、完整资源归属/引用以及 `cleanup_eligible`。`disposition=administrator_decision`
表示历史仍有未知，管理员需据此决定是否签发现有的新执行批准。eligible 只表示
当前限定清理检查满足条件，本身不是许可；已确认活动或当前冲突仍阻断清理。

批准绑定新的 execution、request/preview digest、runtime、cluster/VMID reservation、
完整原清单、新有限截止和原 caller/native 关联。`recovery_of` 是原 native execution；
`pending.execution_id` 是原 caller execution。恢复批准不复用原验收批准。

```sh
iaas run --runtime-config "$RECOVERY_INPUT_DIR/runtime.json" \
  --environment "$RECOVERY_INPUT_DIR/environment-start.yml" \
  --engine local --component pve-template --operation recover --scope cohe \
  --execution-id "$RECOVERY_ID" --output "./recovery-start/$RECOVERY_ID"
```

保留 `recovery-start/$RECOVERY_ID/work/pve-recovery/` 的 request、preview、journal、
result，并检查 `diagnostics/recovery-result.json`。start 在新 work 窗口内重新核清，
cleanup 在新 cleanup 窗口内逐项执行。绝对 UTC 截止和同一起点的相对预算只收紧，
进入 cleanup 不获得新预算；原截止保持不变。

已经派发过的同一 ID 只走 observe。把 observe environment 的
`original_execution_dir` 指向上面的恢复目录，使用新的输出父目录和相同 basename：

```sh
iaas run --runtime-config "$RECOVERY_INPUT_DIR/runtime.json" \
  --environment "$RECOVERY_INPUT_DIR/environment-observe.yml" \
  --engine local --component pve-template --operation recover --scope cohe \
  --execution-id "$RECOVERY_ID" --output "./recovery-observe/$RECOVERY_ID"
```

observe 不使用 API/SSH 凭据、设施网络或新预算。结果缺失、摘要冲突或收集失败保留
unknown，不会回退为 start。需要进一步清理时使用新 execution/preview/批准，提供
已留存的 `previous_recoveries`，保留未缩减的完整原清单及所提供材料的实际字节摘要。
不要求补齐历史链。已留存任务的 UPID 查询失败、状态异常或旧清理响应丢失导致
活动仍无法确认时，必须阻断自动清理；不能用新批准替代当前活动状态核对。

## 权威403、活动及结果边界

拒绝证据须由授权读取的权威服务端记录，或当前批准明确接受的管理员导出提供。
request 声明 source、provenance、保护主体和来源说明。已有独立 dispatch trace 时
可与服务端记录匹配；没有 trace、关联歧义或证据不足则保留历史 unknown，不要求
管理员补造原始记录。文件 hash、当前缺权限、没有 PID 或当前停止状态都不能单独
证明历史请求未执行。仅无 UPID/PID 的旧 guest-exec intent/unknown 关联缺失可在
preview 中交给管理员用现有新批准决定，历史仍为 unknown。当前任务无法核清或
helper 活动未知则显示 disposition=blocked、task_activity_unresolved=true，拒绝
清理，不增加重建证明或全历史闭环门禁。

恢复分别报告原请求核清、`original_activity`、`original_facility_writes`、本次
`facility_writes`、逐项 present/absent/unknown 与 cleanup/collection。权威 guest exec
拒绝只消解该请求活动；clone/configure/start 的原 issued 事实保留。源模板当前改变
或不能查询是独立观察，不重写原 source/验收结果；完整独立克隆清理仍须有自身归属
及完整参考范围。

删除仅针对原 VM/UUID、完整盘集及专属 snippet。VM 已 absent 只表示当前不存在；
独立删残盘仍须证明原/当前归属且无外部引用。stop/delete/helper 响应丢失保留 unknown
并停止依赖操作；观察到 absent 不推定历史删除成功。只有完整清单均被安全确认 absent
且本次写入可判明、结果收集完整，恢复 cleanup 才可 passed；历史 activity/writes
可以继续 unknown。原验收仍保持原 failed/unknown，新的验收
和 caller promotion 需要另一次批准执行。

## infra-ops 承接与发布

infra-ops 需要传递上述 file aliases，保存原 caller pending/consumption 与 native
execution 关联；历史拒绝证据与已有 trace 是可选补充，不要求重建。新增 recover plan、
新批准 start 和同 ID observe 路由，保存并串联后续 recovery 材料。它还须选择配套
launcher/runtime/helper 能力版本并冻结实际 digest/截止；不要改写原 journal、清空
消费记录、删除执行目录或重放旧 acceptance start。本 change 不修改 infra-ops 仓库。

继续使用现有 release 流程发布固定 runtime manifest 与 amd64/arm64 digest，以及
`iaas-linux-amd64`、`iaas-darwin-arm64` 和 SHA256SUMS。发布说明应列明恢复 request v1、preview/result v2、
共享 admission v2、原 v2 仅恢复读取、只读文件/reference helper 要求、实际软件测试
结果与现场结论范围。软件产物发布不等于某次现场恢复完成；已记录的限定结论见验收材料入口。

## 当前登记前恢复与停止诊断

当前验收 preview v2 在原 clone description 中绑定一次性 `clone_marker`。
原成功 UPID、完整空闲目标准入以及 marker 匹配的 candidate UUID/完整
slot→volid 快照必须已经留存；缺字段或部分快照给出 `needs_evidence`，
不能以当前 VMID/marker 补造归属。candidate 尚未 registered-owned，原验收
不会自动 stop/delete。新的只读 plan 联合核对当前 config/content/pool、源模板、
权限与引用和全部相关活动，固定 UUID 与完整卷集到 preview v2 的
`proof_bindings`。新批准只授权该完整原范围；start 重查并拒绝新增盘、UUID/marker
替换、活动未知或 preview/start 漂移，不重放 clone/configure/start/guest exec。

若 VM 在已独立证明的 present-VM preview 批准后、start 前变为 authoritative absent，
可沿用该批准冻结的完整 scope 核验精确孤卷。若为已不存在 VM 重新生成 plan，
必须引用前次恢复材料、相同已证明冻结 scope 和已知不活跃任务；前次活动未知则拒绝。
两种分支均仅处理原范围内精确余项，不再次删除 VM，也不扩充卷集。
没有已证明 scope 则拒绝。原 request/journal/result 保持只读。

验收与恢复结果及 CLI 摘要的 `stop_diagnostics` 按 phase/check/task-or-resource
保留最后必要观察和终止证据；后续 cleanup/source 不覆盖先前 claim 的 volid/vmid、
时间和原因。failed 检查可以与整体 unknown 共存，未观察不是空集合。
软件替身已覆盖同步延迟、暂时查询失败、原 PID、缺证据和部分恢复；这些不是
真实 PVE 验收或日常部署代验。

请求可显式声明 `evidence_mode: registered` 或 `pre_registration`。离线 check 校验模式以及已必填的 original request/journal、caller 关联和完整 UUID/卷范围；不打开原材料、不发现资源、不认定归属。在线 plan/start 要求声明与原 journal 的登记状态一致。省略该可选声明时仍按原 journal 判定模式。
