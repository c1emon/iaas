# 实施与软件验证

实施分支：`feat/pve-observation-executor-and-stop-diagnostics`。

## 已交付范围

| 任务 | 实现及代表性验证 |
| --- | --- |
| 1.1–1.5 | 共享只读 observation、一次冻结预算、分组安全证据；注入时钟验证到期、跳钟、局部限额及终态保留。实际修改先做 impact；高风险和 UNKNOWN 结合直接源码与定向测试核对。 |
| 2.1、3.1–3.2 | publication 同 UPID 及配置、pool、卷容量/归属、template flag、删除消失观察；失败 CLI 输出原生 stop_diagnostics。替身覆盖单次写、pending→ready、明确归属失败、有限 GET 重试和 failed/overall unknown 共存。 |
| 2.2–2.5、3.3–3.5 | acceptance 原 preview nonce/clone description、门禁前候选快照、配置/扩盘/QGA/cloud-init/同 PID 采样、完整清理；recovery 联合原证据与当前独立证明冻结精确 scope，覆盖 VM 存在及删除后孤卷、证据缺失/身份和卷漂移拒绝。历史材料仅受限读取，不增加旧版 start。 |
| 2.6 | saved-plan post-apply 与独立 verify 各一次有限观察窗口；既有截止只收紧、全组共用。不新增 admission 必填字段，不提升历史失败 apply。原生状态、TLS 和外部插件事实独立保留。 |
| 2.7 | snippet 上传 exact-file/digest/inode 及删除后完整引用观察；普通 helper 支持只读 observe，响应丢失保留活动未知，不重发写操作。 |
| 4.1–4.4 | image build/test 简单宿主及当前容器内存观察：已测不足拒绝、缺测量保持 unknown；原任务预算只冻结一次。固定源/checksum 传输有限重试，仅清理本次半成品，不重跑 provider/初始化。 |
| 5.1–5.5 | 当前合同/schema/示例与离线 check 同步，未知 action/参数拒绝，离线不读取远端或规划机容量作执行门禁；调用方清单与当前操作说明同步。提交前执行图变更分析，动态解析限制以直接源码与软件证据补足。 |

## 验证结果

- 变化域集成回归：26 个测试文件，`607 passed, 1 skipped`。覆盖 observation、image、publication、acceptance、recovery、snippet、saved-plan、offline dispatch 与当前合同示例。唯一跳过项为真实进程组终止测试，仅在 Linux 执行器运行；本机 macOS 的权限不足分支用确定性替身验证，保持活动 unknown 并阻止清理。第三方 passlib 的 `crypt` 弃用警告不影响测试结果。
- 最终类型声明修正后的相关回归：`155 passed, 1 skipped`；预算、验证报告、snippet 及 saved-plan 分支保持通过。
- 改动源文件 Ruff 通过；新增/改动行的 Ruff 检查无新增问题，测试文件 6 项既有风格问题保留。改动源文件 Pyright 通过。
- snippet helper `bash -n`、`git diff --check`、严格 OpenSpec 校验通过；合同回归包含当前 JSON schema/示例验证。
- GitNexus impact 与每阶段 detect-changes 已执行。图风险包含 CRITICAL，按调用链核对了预算、执行入口和恢复/清理行为；索引的动态调用与 UNKNOWN 不作为无影响证明。

这证明覆盖的本地软件/替身行为，不证明真实 PVE 状态同步、来宾扩容、设施恢复或生产资格。

## 条件项与调用方承接

初次软件交付时第 6 节授权条件未触发。2026-10-04 用户随后授权 ONE 本地 Docker 构建及最多两次限定真实克隆，已执行并清理本次资源，详见 [真实验收记录](acceptance.md)。常规 DELETE 失败的原结果保持 unknown，两次独立恢复通过；未发布 OCI 版本或执行匿名消费验证，也未修改 infra-ops、代验日常部署。调用方承接见 [适配清单](infra-ops-adaptation.md)。

## 后续授权：存储插件 DELETE 兜底

用户随后明确授权仅在验收清理处增加存储插件兜底：stopped / `unexpected status` 后最多追加两次 DELETE，等待 5 秒、15 秒，原 cleanup 预算不续期。每次重新证明活动停止、原 VM/池/附件及卷归属，未知/冲突拒绝；每个失败 UPID/观察保留，完整清理成功后 stopping 为空。其他写路径不变。

相关六个测试文件 `143 passed`，改动源文件 Ruff/Pyright 与严格 OpenSpec 校验通过。代表性用例覆盖两次间隔、三次上限、共享截止、VM 已消失不重发、未知响应/任务、其他非 OK、活动重新变为 running、UUID/池/锁/卷归属变化拒绝。兜底初次交付时只做软件验证，当时未增加第三次真实克隆或修改此前原始结果；5/15 秒不是经过真实间隔对比验证的最优值。

用户再次授权后，源码 `f3e9a57` 的 ONE 本地 Docker 复验完成：独立新模板、一次真实克隆，六项工作检查及全部清理 passed，overall passed。DELETE 首次即 OK，未触发兜底，因此不提升重试分支的现场证据等级；临时模板/S3 版本/容器/镜像/磁盘/凭据已清理。准备阶段拒绝和原始结果保留，详见 [复验记录](acceptance-retest.md)。未发布 OCI 版本或代验 infra-ops。
