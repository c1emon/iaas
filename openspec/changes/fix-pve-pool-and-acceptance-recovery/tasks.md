# Tasks

实施分支为 `implement/fix-pve-pool-and-acceptance-recovery`；仅按实际完成的工作勾选。本 change 不修改 infra-ops。

## 1. 普通 VM 的 pool 与 VMID 策略

- [x] 1.1 补 inventory 非空 pool 校验、可选 acceptance 区间及互斥/普通 VM 排除，生成和文档保留同一策略；用未指定池、指定池、区间端点/重叠/落入预留区间的 fixture 验证。
- [x] 1.2 将 pool_id 同时传入 protected/unprotected OpenTofu VM resource，保留原资源地址；用 HCL/原生 plan fixture 核验实际参数和 pool_id=null，运行既有 resource parity guard。
- [x] 1.3 在普通 VM saved companions/review 中冻结 pool、策略及具体 VMID，执行前检查绑定/权限/占用和适用的调用方集群/VMID reservation；以池/范围篡改、占用和模拟竞争拒绝验证，更新当前调用示例与串行化说明。

## 2. 共享只读准入和 helper 条件

- [x] 2.1 实现实际有效权限/条件式池授权检查与四类固定权限诊断，覆盖 privilege-separated token、0/1合法授予、缺键/非法值/请求失败/可见性不足；用源/目标/池/存储/网络/任务读的代表性正反例验证并更新权限表。
- [x] 2.2 汇总源身份、节点、storage/容量、network、VMID权威可见性和 SSH/helper 准入；用缺池、无权限、节点/网络冲突和 pool-only 列表不可证明空闲的测试核验克隆/上传/启动前零写入，更新联网预检说明。
- [x] 2.3 给现有 upload/delete helper 增加只读机器能力探测和对应 wrapper-only sudo/bootstrap 文档，证明 create-only/deadline/reference/digest 等必要支持；用本地 helper fixture 核验探测零写入、缺能力拒绝及普通上传回归。

## 3. 模板 publication 与当前模板记录

- [x] 3.1 更新 publication request/v2、preview/result/record/v3，绑定可选 pool，在原生创建请求直接指定池并在结果中核实际归属；用不入池/既有池/不存在或无权池/计划池更改拒绝的 fake API 测试和合同 fixture 验证。
- [x] 3.2 将普通 VM、验收和当前 snippet acceptance-origin 消费校验统一到最新模板/验收合同，更新 schemas/examples/docs，拒绝旧 start 输入且不改 state；运行合同生成一致性及模板消费者定向回归。

  软件证据：合同/验收执行/snippet 消费组合 123 passed；合同与验收执行 Pyright 0 errors。v3 的 plan/start 及固定发布已交付。

## 4. 验收 plan、执行与诊断

- [x] 4.1 增加 action=accept 的离线 check/联网 plan、acceptance request/result v3 和 preview/v1，绑定 pool、验收区间、具体 VMID、runtime 与 deadlines；用无凭据离线成功、缺字段、摘要/镜像/池/范围/截止冲突和零设施写入 plan 测试验证并更新输入文档。
- [x] 4.2 将完整准入用于 plan/start；clone 直接传池，claim/启动/清理前核实际池、权限、UUID和完整磁盘归属；用入池完整验收/精确清理且池保留、被移池或资源变更失败关闭的代表性测试验证。
- [x] 4.3 引入脱敏的明确拒绝和未知请求结果，逐请求消解活动并保留历史 issued；用 guest exec 权威403立即失败且允许安全清理、另有活动未知仍拒绝、超时/丢响应仍unknown与零清理的测试验证，更新固定reason codes和结果示例。
- [x] 4.4 修正 source_changed/source_snapshot_missing/source_query_failed/source_evidence_insufficient，并保留原始 failure_stage/reason；用容量失败无快照、确实身份变化和查询失败测试验证结果与 unknown-first 聚合，更新源一致性说明。

  软件证据：`uv run pytest tests/python/test_pve_template_acceptance.py -q`（30 passed）；`uv run pyright src/iaas/pve_template/acceptance.py`（0 errors）。无现场设施操作。
- [x] 4.5 在 plan/start 克隆前输出总磁盘上限、所需总量与必要明细，检查目标存储容量且继续克隆后核验；用40GiB+4MiB、EFI/TPM代表盘、缺大小证据/存储容量不足测试验证不自动抬高上限，更新容量口径和新计划示例。

## 5. 原验收受控恢复

- [x] 5.1 定义 recovery request/result/preview v1、原 caller/execution/material/全清单关联及受信服务端证据合同，增加 action=recover 的联网核清 plan；用原digest冲突、消费关联不符、记录缺失、有效/不可信/歧义403和未终止任务测试验证零设施写入，提供正式输入示例。
- [x] 5.2 在恢复入口定向读取 rc.19 v2 request/result 和 v1 journal，保持原 bytes/digest/身份/截止，不添加新 pool/区间或修改原 pending/消费；用 run-120-1 同结构脱敏软件 fixture 核验VM798不被新区间阻挡、旧 start 不可重放，并记录其模拟证据边界。
- [x] 5.3 实现新授权/new execution/recovery_of 下的限定 stop/delete/磁盘/snippet 清理，重新核活动/归属/引用和截止，报告逐项存在性及独立本次写入事实；用VM与两盘一snippet清理、池保留、原结果不变、VM已不存在/磁盘引用冲突和响应丢失测试验证。
- [x] 5.4 实现恢复 observe、收集失败/新执行响应丢失和后续新批准的恢复关联；用同ID只能observe、旧预算不刷新、新截止到期拒绝、完整清单不可缩减以及不执行clone/start/guest exec的调用审计验证，更新恢复操作文档。

## 6. Launcher 与调用方交付

- [x] 6.1 更新能力版本、plan action选择、recover start/observe效果及凭据allowlist，完整传递只读原材料/preview/admission；用Go与runtime local/DinD传输fixtures核验缺能力拒绝、请求不被改写、observe无操作凭据、plan无设施写入且不消费批准，并验证新父目录/相同execution basename的命令。
- [x] 6.2 完成最新合同/权限/helper更新说明、run-120-1正式命令及infra-ops适配清单；由当前schema和launcher测试校验示例/文件映射/调用参数，确保不修改infra-ops仓库、不输出敏感证据或提供手改journal等捷径。

## 7. 综合软件验证和固定版本发布

- [x] 7.1 运行范围相符的Python、Pyright、Go、OpenTofu模块/合同一致性、helper和OpenSpec strict校验，提交前gitnexus impact/detect-changes；记录实际结果及已知覆盖边界，不用graph零影响代替测试。
- [x] 7.2 使用现有release流程发布新的固定runtime和配套launcher，核验manifest/platform digest、SHA256SUMS和能力；发布说明填写实际版本/helper要求及软件结果，不提前编造digest或声称现场验收通过。

## 8. 本轮现场恢复验收

用户已于 2026-10-01 决定暂时后置本项；本轮完成软件实施和固定版本交付，不继续现场操作。重启条件见 delivery.md。

- [ ] 8.1 收到原材料、权威403证据及当前限定清理批准后，固定新版digest按正式入口核清run-120-1并精确清理VM798/两盘/snippet；记录实际逐项存在性、完整性和原验收仍未通过，不重放原操作。资料/权限不足时保留unknown与本项未完成，不阻断诚实的软件版本交付。

软件验证：本地 Python 1792 passed、2 skipped；全项目 Pyright 0 errors、Ruff及4/4 import contracts通过；Go含实际runtime集成通过；OpenTofu锁定provider0.111.1的fixture init/validate、模块fmt及OpenSpec strict通过。GitNexus已重新索引并完成提交前检测；代码阶段风险critical，以调用链/源码和回归测试核边界，不将graph零影响当作验收。

固定 rc.20：release工作流36862950966全部成功；amd64/arm64各2093 passed、4 skipped；匿名digest拉取及capabilities平台调用、registry manifest/platform摘要、两个launcher SHA256SUMS和macOS版本输出已核。实际值见[delivery.md](delivery.md)。API/helper与local/DinD传输均为软件fixture，没有现场设施结论；仅8.1未完成。
