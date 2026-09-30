## 1. 合同与绑定

- [ ] 1.1 更新两个 request/result 到 v2，定义严格 UTC deadlines、排序、deadline_outcome/reason codes 及独立本次 facility_writes 事实，保留 unknown 优先与更严格相对上限。
- [ ] 1.2 为两个操作增加 admission deadlines 精确匹配及 request digest/execution 身份绑定，持久化 request/admission/journal/result；不影响普通操作。
- [ ] 1.3 更新生成的 JSON schemas、能力声明、合同文档和共享正反 fixtures；launcher 拒绝缺能力或旧版本，不自动补期限。

## 2. 原生与 helper 执行

- [ ] 2.1 在同一 start 时间基准同时冻结 work/cleanup monotonic 上限，后续只能收紧；实现阶段、每次发送前检查，覆盖 intent 持久化后重查和 API/guest/内部重试/轮询 timeout。
- [ ] 2.2 验收工作到期转入限定清理，清理到期停止新写入，保留任务、残留及未知事实；不改变原有所有权/活动冲突门禁。
- [ ] 2.3 独立 cleanup 实现 work 准入/cleanup 写入窗口、逐项截止；helper v2 按固定调用模式要求 cutoff，验收上传和删除不可降级，普通上传语义不变；远端 create/unlink 前最终检查，更新节点 bootstrap 文档。
- [ ] 2.4 observe 校验原冻结期限且只读；新授权补清理保留原全清单并验证活动终止，不延长或重写旧执行。

## 3. 定向验证

- [ ] 3.1 覆盖时间格式/日历/顺序、缺字段、admission/材料期限篡改、准入已到期及恰好 cutoff；确认 admission/rejected、本次零设施写入、未检查存在性 unknown 和整体 unknown 可同时表达，不补造库存。
- [ ] 3.2 覆盖阶段迟到、持久化期间到期、内层 timeout 上限、工作到期转安全清理、清理逐项到期，以及工作期间 UTC 后跳随后进入 cleanup 不扩大 start 冻结上限。
- [ ] 3.3 覆盖在途 API task/guest/helper 超时与丢响应、远端迟到/锁后到期；确认不伪称取消、不删未知资源、清理成功不提升验收失败。
- [ ] 3.4 覆盖到期 observe 零副作用、恢复不刷新窗口、新有效授权 retry 及旧/无效授权拒绝，local/DinD 文件传输保留期限。
- [ ] 3.5 运行范围匹配的 Python/Go、schema 同步、静态检查、OpenSpec strict；提交前 GitNexus impact/detect-changes，记录实际覆盖边界。
- [ ] 3.6 覆盖验收上传/删除模式缺截止字段拒绝、验收不可降级普通模式，并增加一条普通 VM cloud-init 上传回归。

## 4. 固定版本交付

- [ ] 4.1 更新版本说明与 infra-ops 消费示例，明确 caller 计算期限、原生执行检查、helper 升级要求及证据边界。
- [ ] 4.2 通过现有 release 流程发布新的 runtime 和 launcher，核对实际产物、manifest/platform digests、SHA256SUMS 和 v2 能力；不覆盖历史版本。
- [ ] 4.3 记录可固定消费的版本/摘要与软件验证结果；不将发布或 fixtures 表述为真实设施验收。
