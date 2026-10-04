实施分支：`feat/pve-observation-executor-and-stop-diagnostics`。软件任务 1–5 已完成，证据见 [implementation.md](implementation.md)。第 6 节已完成授权范围判断：本次未授权发布或真实设施验收，条件未触发；勾选表示条件处理完成，不表示这些操作已执行。

## 1. 当前合同与共享观察组件

- [x] 1.1 确认对应实现分支并按 AGENTS.md 取得必要切换确认；对实际修改符号执行 GitNexus impact，核对 UNKNOWN／高风险结果及直接源码。
- [x] 1.2 仅更新字段或语义实际变化的当前 request/preview/admission/journal/result/schema 与必要版本，绑定发布 work/cleanup 截止及 acceptance preview 的 clone marker；普通只读 verify 不增加必填审批／截止字段，不新增旧版启动适配。
- [x] 1.3 实现只读 probe／域分类／既有预算／安全证据 sink 的观察执行器，不接受写派发回调；复用单次 transport 和 DeadlineBudget。
- [x] 1.4 明确各适配器 transient/pending allowlist，区分权限、TLS、非法响应、归属冲突、非 OK 任务与缺失终态信息。
- [x] 1.5 验证同一 UPID／PID、局部限额只收紧、同一起点双窗口／独立只读单窗口、跳钟、到期不再在线查询或写派发；image 相对 task timeout 只在原启动时转换一次。

## 2. PVE 任务成功后的状态检查

- [x] 2.1 接入发布上传／导入／转换与 cleanup/retire 任务和目标状态观察，覆盖 identity/pool/disk/template flag/容量及消失。
- [x] 2.2 acceptance plan 生成一用 nonce 并绑定 preview，原 clone description 携带 marker；原 UPID 成功后在 pool/content 门禁前保存 marker 匹配的 candidate UUID／完整 slot→volid 快照及必要 content 字段（volid/vmid/size），不全视图标 incomplete，完整证明前不登记 owned，不另写 marker。
- [x] 2.3 接入配置／扩盘收敛及 QGA/cloud-init 就绪；exec-status 只查原 PID，前次已退出才能发下一次固定只读采样。
- [x] 2.4 对来宾根分区／文件系统、身份、地址／网关／DNS定义 pending 与明确失败边界，保留失败前必要事实。
- [x] 2.5 接入 acceptance/recovery 删除后 VM 和完整卷集消失等待，覆盖“查询成功但对象仍在”，保留外部插件失败，不重复删除。
- [x] 2.6 接入普通 PVE saved-plan 验证的绑定身份／资源池／配置／容量／消失等待；post-apply 验证组与独立 verify 在各自入口用已有适用 timeout 或内部默认 120 秒冻结一次预算，所有对象／probe／retry 共用，已有显式绑定截止只收紧。测试无新增deadline字段仍可验证、已结束原窗口后的独立核验、跨对象／重试不续时、较紧既有截止和原生事实独立；不新增 apply 拒绝门禁，不取消或重跑 provider。
- [x] 2.7 接入 snippet 上传／删除后 exact-file/digest/inode 与完整引用核验，仅重查；helper 响应丢失不等于远端结束。

## 3. 证据、停止诊断及登记前恢复

- [x] 3.1 实现按 phase/check/resource-or-task 分组的有界判定证据与 schema 化原生 stop_diagnostics／CLI 摘要：完成阶段、停止检查、写与任务活动、归属／存在性、清单完整性、逐检查最后必要／冻结终态证据与恢复支持／资格／所需证据，不用全局单槽。
- [x] 3.2 验证 failed 检查与 overall unknown 可共存，未观察不等于空集合，收集失败／缺终态仅给已有事实；claim 两卷失败后继续 cleanup/source，最终诊断保留原 volid/vmid/time/reason 与后续各组证据，安全字段不泄露敏感材料。
- [x] 3.3 实现 recovery registered/pre-registration 只读校验；以原 preview/clone marker、成功 UPID、空闲目标准入、完整候选 UUID／slot→volid 与当前相同 config/content/pool/source 联合规则固定可恢复正例，证据不足明确 needs_evidence，不按当前 VMID／marker 单独认领。
- [x] 3.4 将完整证明范围与 proof bindings 冻结到新 preview，要求新有限批准；VM present 时 start 重查 marker/UUID/完整卷，VM authoritative absent 时要求已独立证明的完整冻结 scope 与必要前次恢复关联，再核当前精确余项／活动／引用／权限，旧证据不修改、不重删 VM。
- [x] 3.5 验证缺原 marker／UPID／完整候选、VMID 复用／UUID 或卷集新增替换／归属冲突、活动未知、preview/start 漂移均拒绝；覆盖部分恢复删 VM 后原卷仍在、冻结 scope 缺失／前次活动未知两类分支；新恢复不重放 clone/config/start/guest exec。

## 4. 镜像与依赖执行边界

- [x] 4.1 实现简单 build/test 内存观察：宿主 MemAvailable、当前容器直接可读的 limit/usage，与 guest memory_mib 比较；记录请求／已测余量／时间／scope，已知不足拒绝，缺数据标 unknown 单独不阻断。不要求全祖先扫描、两代兼容资格或独立开销策略。
- [x] 4.2 验证已测宿主不足、容器余量更紧时无客体派发；无限制／缺测量／不支持布局不会伪装容量充足，unknown 单独不阻断，独立已知不足仍拒绝，实际构建成功不补写容量 passed。
- [x] 4.3 为已固定版本／来源／checksum 的镜像与既有依赖传输接入有限只读重试，清理仅本次半成品，锁选择不变；checksum／权限／TLS错误不重试。
- [x] 4.4 明确 native dependency 工具已有下载机制和可重试边界；不重试整个 provider apply 或含后端设施副作用的初始化。

## 5. 离线检查、代表性测试与文档

- [x] 5.1 更新受影响 action 的 check 与关键正反例：当前版本、publication 双截止、preview marker 与候选证据模式、能力和未知参数；普通 verify 不要求新增审批字段，声明检查不使用规划机内存作远端容量门禁。验证零网络／凭据／provider初始化／设施写操作，区分离线格式与运行时观察。
- [x] 5.2 使用注入时钟与定向替身覆盖 pending→ready、允许的查询错误、明确失败、单次写计数、同任务关联、预算到期、失败前证据和诊断；不穷举同质对象。
- [x] 5.3 对实际变化域运行代表性软件回归、必要 schema 校验和静态检查，覆盖模板／克隆／恢复／snippet／saved-plan 相关行为；不把全量镜像重建或所有真实主线设为每次变更门禁。
- [x] 5.4 更新调用方适配清单和接口说明，分别说明离线有效、软件验证、真实验收、日常部署；外部插件故障和未知结论保持如实。
- [x] 5.5 实施提交前执行 GitNexus detect-changes 并处理 partial/truncated/UNKNOWN，不以索引空结果证明无影响。

## 6. 后续授权下的发布与限定真实验收

- [x] 6.1 若实施授权包含固定版本发布，完成既有 OCI 发布／匿名消费校验并记录固定 digest；未执行则如实标明未发布。
- [x] 6.2 实施 C 级真实验收前确认授权和精确设施范围：复用既有专用池／源模板，最多两次顺序临时克隆，额外 S（≤1 天）；无授权则仅交付软件结论。
- [x] 6.3 获授权后验证正常全克隆、首次启动前独立网络／身份、128 GiB 来宾自动扩容、QGA/cloud-init、源模板不变和精确清理；临时错误仍使用替身注入。
- [x] 6.4 获授权后在本次临时资源上验证可证明的登记前停止、新只读 recovery preview、限定批准、exact cleanup；无法证明关联时验证拒绝并如实报告，不猜测归属。
- [x] 6.5 清理仅本次授权临时资源，保留原始证据；分别记录软件交付、真实覆盖和 infra-ops 日常部署未代验范围。

第 6 节结果：6.1 按用户要求未走 CI/OCI 发布；6.2 后续取得 ONE 本地构建及两次限定克隆授权；6.3 六项真实工作检查通过、常规 DELETE 失败，因此原验收整体 unknown，新独立恢复通过；6.4 登记前停止及新独立恢复通过；6.5 本次 VM/模板/卷/snippet/S3 版本及容器/镜像/凭据已清理，原始证据保留。具体覆盖、修复和未通过项见 [真实验收记录](acceptance.md)，未代验 infra-ops 日常部署。

## 7. 用户追加授权：验收 DELETE 存储插件兜底

- [x] 7.1 仅在 acceptance cleanup 原任务 stopped / `unexpected status` 后，最多追加两次 DELETE，等待 5 秒、15 秒；复用原 cleanup 预算，每次重新证明活动停止、原 VM/池/附件/卷归属。其他错误、未知活动或证据不足不重试。
- [x] 7.2 保留每次失败 UPID/观察；对象已消失不重发；最终清理成功与历史任务失败分别表达，成功后 stopping 为空。
- [x] 7.3 定向测试验证次数、间隔、截止、失败保留、未知/冲突拒绝；注释和合同明确标注存储插件兜底，其他设施写路径不变。不额外创建真实资源，既有真实记录不改写。
