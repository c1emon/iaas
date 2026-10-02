# 规格复核记录

2026-10-01 规划复核时，核对本轮需求、main源码/主规格及上游权限与provider合同。下列规划检查保留为历史记录；当前软件实施状态见末节及 tasks。

## 需求覆盖

| 原需求 | 规格落点 | 任务 |
| --- | --- | --- |
| 1. 三类VM pool | foundation普通pool、lifecycle模板pool、acceptance强制pool/实际归属/池保留 | 1、3、4.2 |
| 2. 验收VMID预留 | foundation区间及端点、saved-plan集群/具体VMID预留互斥、recovery原VM798 | 1、5.2 |
| 3. 完整准入/存储权限分类 | online-preflight有效权限/条件式/完整helper准入/固定分类，plan与start复核 | 2、4.1 |
| 4. 拒绝与未知 | acceptance逐请求消解、403与丢响应分开、保留此前写入 | 4.3 |
| 5. rc.19受控核清清理 | recovery完整原清单、受信403关联、新授权有限窗口、无原操作重放、独立结果 | 5、8.1 |
| 6. 源一致性诊断 | acceptance四类源原因、缺快照unknown及原始失败保留 | 4.4 |
| 7. 总容量口径 | acceptance系统/附属盘合计、clone前plan/start拒绝、明细与重新批准 | 4.5 |
| 8. 验证/版本交付 | 各组代表性软件验证、launcher/helper要求、release实际摘要、现场结论分开 | 6、7、8.1 |

## 已修正的设计问题

- 用原生条件式检查VM.Allocate和guest权限，不错误要求VMID/池双授权或Audit/Unrestricted重复授予；权限值0不当作未授权。
- 普通VM与新验收/publication使用稳定集群范围绑定，防止同集群不同node endpoint绕开同号预留；互斥由调用方既有机制承担，不宣称IaaS建了全局锁。
- 用现有受限helper补充完整VMID可见性，只有证据仍不足时才拒绝，避免pool-only身份被不必要的全局API授权要求阻挡。
- 新preview完整快照和摘要保存在journal，明确新one-shot admission/v2与原证据v1的解析边界，使observe及当前snippet消费者可验证批准关联。
- 修正恢复命令的output路径，保持现有basename=execution_id约束，观察使用新父目录与相同新恢复ID。
- VM798恢复不补pool、不套新区间、不刷新旧截止、不修改原结果；当前源状态不成为独立克隆清理的额外依赖，也无需补guest exec权才能清理。
- 不把预检/软件fixture/发布当作现场恢复完成；原资源精确ID来自受保护材料，当前文档没有猜测磁盘/snippet身份或声称旧验收通过。

## 规划时校验结果

- `openspec validate fix-pve-pool-and-acceptance-recovery --strict`：通过，无issues。
- 将7个delta在临时目录合并到对应主规格后strict验证：7/7通过，无ERROR/WARNING；存在长requirement文本的INFO提示。
- 自动核对MODIFIED标题存在且唯一、原有场景保留、ADDED不与主规格重复、相对链接有效、任务编号唯一且22项均未勾选：通过。
- 规划时只新增本change目录；主规格、源码、infra-ops及现场资源未修改。规划完成不代表实施完成；task8.1只有真实材料、有效限定批准及实际逐项结果就绪后才能完成。

未发现阻断本次规格定稿的问题。实际pool、原资源UUID/volid/snippet、受信日志材料、新清理截止和发布digest是后续运行/交付输入，不能在规格阶段编造。

## 实施复核

实施分支 `implement/fix-pve-pool-and-acceptance-recovery` 已分阶段提交 pool/VMID、publication 最新合同、拒绝分类、源诊断以及验收 preview/准入。恢复入口、launcher 和示例按当前合同交付；软件校验结果记于 tasks。

本 change 没有修改 infra-ops、OpenTofu state 或现场设施。当前固定产物为 rc.25，活动未知阻断清理、完整必要权限、历史冒号引用、review传输及provider空pool等修正和发布验证见[delivery](delivery.md)。task8.1的完成状态引用调用方的新恢复记录；原验收仍未知。软件fixture、只读预检或发布成功均不替代现场结果，材料定位与证据边界见[验收材料入口](../../../../docs/operations/pve-lifecycle-acceptance.md)。
