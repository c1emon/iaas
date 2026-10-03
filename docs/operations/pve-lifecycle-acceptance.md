# PVE 生命周期验收材料

更新日期：2026-10-03。本页是 IaaS 的材料与结论入口；操作步骤仍以对应手册为准。最新软件为 [rc.26](../../openspec/changes/archive/2026-10-03-fix-pve-template-check-action-dispatch/delivery.md)，修复模板 check 的 action 分派。下列历史现场证据使用 rc.25，完整镜像/launcher 摘要与发布检查见[rc.25交付](../../openspec/changes/archive/2026-10-02-fix-pve-pool-and-acceptance-recovery/delivery.md)。

## 当前结论及边界

| 范围 | 已有证据 | 能够说明的结论 |
| --- | --- | --- |
| IaaS软件与产物 | rc.25两个平台各2132 passed、4 skipped；实际镜像保存计划准入、匿名消费、launcher校验通过 | 配套软件与产物验证通过，不代替现场验收 |
| rc.26软件修复与产物 | 两个平台各2145 passed、4 skipped；实际镜像保存计划准入、匿名消费、launcher校验通过 | action分派修复已交付，不代表模板9006退役或现场最终收尾完成 |
| 原run-120-1受控恢复 | 调用方记录新恢复 `recover-run-120-1-20261002-01` 清除VM798、两盘和snippet | 原验收仍未知，9004保留但不可用；不是重放原操作 |
| 模板9005 | 调用方记录六项原生检查、临时资源清理通过及record/v3 available | 限定模板验收通过，不包含应用或压力测试 |
| 普通VM与独立清理 | 调用方记录rc.24创建关机VM799，rc.25删除、state写回和新批准专属snippet清理；最终无残留/pending | 限定普通VM生命周期闭环，未执行普通VM guest/业务验收 |

现场结论来自调用方的[验收总结](../../../infra-ops/docs/operations/deployment-lifecycle-validation.md)和[证据索引](../../../infra-ops/docs/operations/rc22-template-lifecycle.md)。IaaS不复制维护其原始执行记录。收尾属于2026-10-02观察，不能推断未来状态；本轮有恢复和补清理，不代表最终版本完成一次完全无人工恢复的正常路径，也不授权日常root接管或新设施操作。

## 材料定位与保留

| 材料 | IaaS入口 | 保留方式 |
| --- | --- | --- |
| 当前固定版本、checksum、CI结论 | [delivery](../../openspec/changes/archive/2026-10-02-fix-pve-pool-and-acceptance-recovery/delivery.md)、对应GitHub Release | 当前摘要完整保留；旧版本只保留关键变化/失败及权威链接，完整旧值仍在Git历史与发布资产 |
| 需求、设计取舍和任务完成 | [change入口](../../openspec/changes/archive/2026-10-02-fix-pve-pool-and-acceptance-recovery/README.md)、proposal/design/specs/tasks/review | 保留设计与责任边界，任务只记录完成条件，阶段性重复统计精简 |
| 当前操作要求 | [PVE](03-pve.md)、[原验收恢复](pve-acceptance-recovery.md)、[snippet清理](pve-snippet-cleanup.md)、[调用方适配](../../openspec/changes/archive/2026-10-02-fix-pve-pool-and-acceptance-recovery/infra-ops-adaptation.md) | 完整保留文件映射、批准/归属/截止/只读观察和失败关闭规则；历史实例不作为授权 |
| 机器合同与合成样例 | [acceptance/cleanup schema](../../automation/schemas/pve-acceptance/v3/README.md)、[recovery schema](../../automation/schemas/pve-acceptance-recovery/v1/README.md)、[验收fixtures](../examples/pve-acceptance/README.md)、[恢复fixtures](../examples/recovery/README.md)、[cleanup合同](../contracts/pve-acceptance-cleanup-v2.md) | schema、示例和生成一致性原样保留；目录版本不等于其中所有合同版本；synthetic不是现场成功证据 |
| 软件正反例与传输验证 | tests/python的PVE合同、saved-policy、saved-plans、acceptance/recovery及helper测试；automation/launcher的local/DinD与runtime集成 | 原样保留，包括权限不足、活动未知、响应丢失、材料冲突和零写入反例；同质集合不逐文件复制清单 |
| 实际镜像发布验证 | [.github/workflows/oci-release.yml](../../.github/workflows/oci-release.yml)、automation/oci/checks、launcher/runtime源码 | 保留可重跑的现有流水线与标准报告，不新建逐对象manifest或额外证据门禁 |
| 历史开发/只读验证 | [本地开发验证](../development-validation.md)、[历史Runtime验证](../runtime-adaptation-validation.md) | 保留环境、代表性结果、限制和来源；不把旧CA/模拟DinD/临时服务结果提升为当前固定版本现场资格 |
| 真实原始材料 | 原request/plan/review/批准/consumption、caller/native journal/result、拒绝证据、恢复关联及原索引 | 在原受保护存储完整保留字节和已有摘要；不复制到仓库、不格式转换，不由当前资源状态补造旧结果 |

本轮仅整理IaaS Markdown。源码、schemas、fixtures、测试、工作流和受保护输入不变；没有清除/tmp工作副本、执行目录、凭据、日志原件或设施资源。工作副本不是权威归档，本文不把本机临时路径当唯一恢复定位。

## 保留的关键问题

| 问题 | IaaS处理及必要历史价值 |
| --- | --- |
| guest exec权限/旧请求未知 | 完整接口权限预检；明确拒绝与可能派发但丢响应分开；新限定恢复保留原验收未知。当前活动查询失败绝不能由管理员批准代替核对 |
| 存储权限/源一致性诊断 | 缺权限、非法值、查询失败、证据不足分开；无源快照返回source_snapshot_missing，保留原容量拒绝。软件反例通过，相关诊断分支未全部现场独立复验 |
| 历史caller引用含冒号 | rc.22只允许pending/reservation保留命名空间，plan/execution ID限制及原journal精确绑定不变 |
| 保存计划漏review.json/discovery原因覆盖 | rc.24完整传输原review，缺失/冲突在设施写入前拒绝；failed discovery保留安全原因，ready仍严格绑定身份 |
| rc.23镜像集成失败 | 测试漏传执行UID:GID，rc.24与正式launcher对齐；保留失败工作流，不降低文件所有权检查 |
| provider空pool误报 | rc.25统一普通VM的空字符串/null语义；真实池权限和验收必填池不放宽，历史state/批准不改写 |
| rc.25模板退役check误用发布校验 | `check action=retire/cleanup` 固定按publish校验，合法请求被拒绝；[rc.26修复交付](../../openspec/changes/archive/2026-10-03-fix-pve-template-check-action-dispatch/delivery.md)按action选择输入和校验器，保持离线、无设施写入。模板退役及最终现场收尾仍由调用方执行 |

caller参数、通知、数据库和工作流的验收材料由调用方维护；本页不扩大为那些系统的验收记录。后续变更按实际风险选代表性回归，不因本次整理新增全套重验要求。
