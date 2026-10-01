# infra-ops 适配清单

这是 IaaS 对调用方的接入要求，不授权修改 infra-ops。当前源码入口、[schema](../../../automation/schemas/pve-acceptance-recovery/v1/README.md) 和[正式操作说明](../../../docs/operations/pve-acceptance-recovery.md) 已交付；固定版本/digest仍以发布核验结果为准。

| 调用侧适配 | 接入要求与可核对结果 |
| --- | --- |
| 固定产物 | 固定新runtime manifest digest和平台、配套launcher及校验值；检查当前publication、acceptance、recovery、绝对截止和helper能力，不使用latest或自动降级 |
| 既有池 | 管理员预建池并在实际用户/token上授予完整有效权限；普通/模板VM pool可选，验收pool必填；不把入池当作所有权证据 |
| VMID策略 | 同一集群同时更新普通inventory与验收请求；本站验收[500,550]、实验[551,800]仅作调用方配置；计划冻结具体VMID、池和完整区间，不现场改号 |
| 同号互斥 | 在已有持久化消费/预留与串行化机制中按稳定集群身份/VMID原子拒绝冲突，同集群不同节点endpoint映射同一scope；vmid_reservation绑定精确VMID集合及原reservation/context；覆盖普通VM/publication/acceptance/recovery，unknown不得当成释放依据 |
| 验收计划/批准 | 先调用action=accept的离线check与联网plan；展示固定资源/容量/权限结论；批准plan_digest绑定preview_digest，并保留request_digest、runtime、deadlines和当前execution关联 |
| 发布记录 | 当前publication输入和模板记录统一按新合同；普通VM和新验收消费record/v3，不转换旧记录、不改OpenTofu state |
| 截止 | 从合法目标开始和批准策略冻结work/cleanup；迟到不能刷新；40GiB总上限不足时修改disk_limit_bytes并生成新的计划和批准 |
| 首次dispatch | 现有pending/消费记录原子记录首次发送；同execution重复只observe，保留完整diagnostics/execution和关联材料，换Runner/output目录不得重放 |
| 诊断展示 | 展示固定reason_code、阶段、必要对象/操作/权限、HTTP状态、容量总量；保留原始失败与清理事实，不将未知降为成功；不展示token/认证头/原日志/guest输出 |
| 原执行核清材料 | 只读提供原acceptance request/journal/可用result及原计划/caller/native持久化关联；拒绝证据和已有trace可选，缺失不要求重建，保留历史unknown |
| 新清理批准 | recovery plan后使用现有新execution_id/recovery_of批准；preview显示administrator_decision时由管理员决定是否处置，绑定完整范围/runtime/截止，不新增批准字段或证明门禁，不恢复原验收预算 |
| 恢复结果消费 | 新recovery结果独立入账，保存原执行created_by、逐项清理/存在性、collection和unknown；安全地记录原pending核清结论，保留原记录与消费历史，不删除或清除以允许重跑 |
| 后续验收/推广 | 清理成功不改原验收，也不推广模板；新的完整验收必须新VMID选择、新plan、新批准和新execution；全部check/cleanup/collection达标再按调用方政策推广 |
| 节点helper | 在调用前按新版说明安装upload/delete helper及最小sudo规则，固定SSH目标与known_hosts/key；用只读能力检查证明必要功能，禁止借bootstrap隐式写设施 |

## run-120-1 恢复示例的固定关联

- plan_id：`run-120-1`。
- 原 infra-ops execution_id：`01591395-b75d-4108-a19d-7e5ccdb99acc`。
- 原 native acceptance execution_id：`01591395-b75d-4108-a19d-7e5ccdb99acc-accept`。
- 原版本：`v0.1.0-rc.19`；源 `cohe/VM9004`，临时 `cohe/VM798`。
- 服务端 guest exec POST 权限403时间：`2026-10-01T16:54:06+08:00`，即 `2026-10-01T08:54:06Z`；仅描述调用方提供的现场事实，实际来源和唯一关联须由恢复核清验证。
- 清单中的VM UUID、两个volid、snippet file_id/digest从原材料精确读取，不以这里的VMID、数量或文件名猜测。新版读取原证据，不补池、不迁移VM、不刷新原截止。

## 正式调用形式

以下入口已由软件fixture验证，现场运行仍需核心原材料、当前限定批准和有效现场条件；403/trace是可选辅助，历史未知由管理员据preview决定。环境文件使用files.recovery_request、files.original_execution_dir、files.cleanup_evidence_dir；start另外映射files.recovery_preview和files.execution_admission，并使用固定新runtime配置。

```sh
iaas run --runtime-config runtime.json --engine local --environment recovery-plan.yml \
  --component pve-template --operation plan --scope cohe \
  --output results/recovery-plan

iaas run --runtime-config runtime.json --engine local --environment recovery-start.yml \
  --component pve-template --operation recover --scope cohe \
  --execution-id '<new-cleanup-execution-id>' --output 'results/recovery-start/<new-cleanup-execution-id>'

iaas run --runtime-config runtime.json --engine local --environment recovery-observe.yml \
  --component pve-template --operation recover --scope cohe \
  --execution-id '<new-cleanup-execution-id>' --output 'results/recovery-observe/<new-cleanup-execution-id>'
```

plan环境的options.action=recover；start的options.execution_mode=start；observe的options.execution_mode=observe、files.original_execution_dir映射新恢复执行的work/pve-recovery且无操作凭据。两条execution-id占位符替换为同一个实际新ID；保留output basename=execution_id，observe用新的父目录。原验收材料与新恢复输出必须分离，且不能覆盖。正式JSON/YAML样例见[恢复样例](../../../docs/examples/recovery/README.md)，其身份/摘要/截止均为合成值，不能直接用作现场批准。
