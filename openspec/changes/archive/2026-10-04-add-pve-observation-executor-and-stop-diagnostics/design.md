# Design

## Context

见 proposal.md。当前 acceptance/recovery 已有冻结 work/cleanup 的 `DeadlineBudget`、写前 intent、UPID/PID 和只执行一次的写边界，适合复用。缺口主要在任务查询短暂失败及任务结束后的目标状态：`claim` 完成全部检查后才登记资源，`configure` 与若干 cleanup 检查立即读取；guest exec-status 查询失败会停止。publication 的 `_upid` 每次另起局部计时。image executor 目前只检查平台、KVM 和磁盘。

此前本地替身复现了短暂缺 pool／卷行、任务或 exec-status GET 500、删除后清单仍显示对象时的提前停止，写操作没有重复。该证据说明观察缺口，不能证明真实 PVE 的同步时延。现有 `bounded-http-read-transport` 明确执行单次已准入请求且不自动重试，本设计保持传输层边界；后续用户单独授权的 acceptance cleanup DELETE 存储插件兜底在域层实施，见下文。

## Goals / Non-Goals

目标是让同一任务／资源在原预算内获得可靠判定，失败时留下可解释且安全的最少事实，并支持有独立身份依据的登记前恢复。

不建立持久作业调度器、自动回滚、通用工作流 DSL、通用设施写操作重试器、全量日志审计服务或资源预留系统。不接管 infra-ops，不修复外部插件，不将当前配置当作历史 apply 成功。唯一域层写重试例外是用户授权的验收清理 DELETE 存储插件兜底。

## Decisions

### 1. 一个观察执行器，三种用途，写派发在外部

组件接收固定观察关联、只读 probe、域判定器、现有预算与安全证据 sink。用途分为 task completion、state convergence、read-only retry；公共机制共用，域判定保持独立。返回 ready、pending、failed 或 unknown 的判定及必要证据。pending 是预算内的暂未就绪；截止后的未确认状态是 unknown，不能伪装成已失败任务或成功。

组件不接受 mutation／dispatch callback，不重新调用整个阶段。`clone/resize/start/delete/upload/unlink` 仍在原写边界先记录 intent、再派发一次；观察器仅绑定收到的 UPID/PID 或已冻结资源身份。未知写响应不能通过重发来获得关联，也不能以扫描到相同 VMID 自动补出任务关联。

备选的每处加 sleep／retry 会重复截止和错误分类逻辑；包装整个操作又会重放写操作，均不采用。域适配器允许暂缺字段或旧视图，但有明确归属冲突时立即结束。对原生任务，只有 `stopped + exitstatus=OK` 证明成功；`stopped` 缺失终态信息属于尚未确认，明确非 OK（包括 `unexpected status`）立即结束该任务检查并保留失败。下述兜底可新建一次 DELETE 尝试，不能改写该失败检查。

### 验收清理 DELETE 的存储插件兜底

2026-10-04 ONE 实测中常规删除任务 stopped / `unexpected status`，后续独立恢复使用相同 DELETE 参数成功。用户随后明确授权仅对此处增加重试。代码注释与文档必须标明这是**存储插件兜底行为**，不能声称修复了插件或已经确认具体故障根因。

仅 `Acceptance.cleanup` 删除已登记的本次临时 VM：最多总计 3 次 DELETE，第一次失败后等待 5 秒，第二次失败后等待 15 秒。间隔从收到明确失败终态后计算；采用固定间隔，适合当前单资源串行清理，不新增配置项或随机抖动。5 秒提供短暂恢复机会，15 秒降低连续失败时的请求频率；这是一项暂定策略，没有真实间隔对比试验证明最优。等待、核对、每次任务轮询与消失检查共用原 cleanup 绝对截止及局部 timeout，余额不足时只等到余额耗尽，不发送下一次 DELETE。

必须保留原 UPID 的明确 stopped / `unexpected status`。等待后重新核对该任务终态、VM 已停止且无锁、原 UUID／池／完整附件，以及完整存储清单中所有原 volid 的匹配 vmid。对象已消失则不重发，但仍确认卷及 snippet 全部消失，并区分资源消失与原任务成功。其他非 OK、响应丢失／未知 UPID／活动未知、归属漂移／缺证据均停止；不再 stop、修改配置或补删孤卷来促成重试。每次使用新 UPID，复用原 journal/分组 observation 保留失败证据。最终清理全部通过时 stopping 为空，历史失败仍保留；耗尽后 overall 继续按失败／未知汇总。

不扩大到 publication、retire、recovery、clone、stop、resize、guest exec、snippet 或传输层。原 ONE 真实记录不重写；新增策略由定向软件测试验证，未增加第三次真实克隆。

### 2. 固定预算与窄重试分类

接受 existing work/cleanup budget；publication 新当前合同将绝对截止绑定 request/preview/admission/journal/result，使用同一 UTC／monotonic 起点冻结两窗。局部超时只能收紧一次，不能在每次 probe 重设。每次传输／SSH／响应读取／退避都受剩余时间限制，截止后不再发在线查询或写操作。复用现有 clock 注入验证前后跳钟；不承诺底层无法抢占的调用在无限精度内终止。

普通 saved-plan apply 的 post-apply 验证组在进入验证时建立一个只读观察窗口；独立 verify 在本次调用起点建立自己的窗口。使用本路径已有适用的有限 timeout，没有则用当前版本内部默认 120 秒，在各自入口从同一 UTC／monotonic 参考点冻结一次 cutoff。整个验证组的所有对象、查询与重试共享同一 budget，不能每个对象／probe 重新计时。所在操作若已有显式绑定的绝对截止，则取更紧值且保持原绑定。result／verification report 记录实际窗口来源、起点和 cutoff。普通 execution admission 不增加 `verification_deadline_at`，独立 verify 不增加必填 `observation_deadline_at`；不因为缺少这类新增字段或只读窗口设定而拒绝原本有效的 apply。

独立 verify 继续绑定原 plan、execution/native output/state 和 expectation，但不会把原已结束观察窗口当作新查询的截止，不续原写权、不要求新的设施写批准、不修改原 admission/result，也不推断原 apply 成功。到期只停止当前在线查询，原生 execution/state/collection 事实独立保留，不取消或重跑 provider；本地 read/observe 仍只读取原材料且不构造预算。局部 probe cap 只在观察开始时收紧，重试不续时。image 既有相对 execution timeout 则在原 task 启动时只转换一次为有限观察上界，不能进入下载／测试子阶段再重置。

固定适配器定义可重试的临时传输失败／明确允许的 HTTP 状态及 pending 原因。不能按异常基类或 `http_status=None` 全部重试；需要区分 timeout/reset、TLS 信任错误、拒绝、无效 JSON／字段、响应限额和未知写结果。401/403、非法输入、明确归属／引用冲突、任务失败立即结束当前检查；任务失败仅允许上述域层 DELETE 兜底例外。503 等只有对应只读 probe 准入后才允许重查。缺权限的 404 不能当作不存在。

`agent/ping` 虽是 POST，语义可为观察；`agent/exec` 派发仍在组件外。已取得 PID 的 exec-status 查询仅查同一 PID。只有此前只读程序已明确退出，才可在原预算内启动下一次固定只读采样程序；PID／响应未知时停止派发。探测行为、证据和查询错误分开，避免一次 GET 失败误记为新 guest exec。

### 3. 域适配与收敛范围

| 检查点 | 固定关联／可等待项 | 立即停止项 |
| --- | --- | --- |
| 镜像、依赖下载 | 固定版本／对象、期望大小／checksum；临时传输错误，清除本次局部半成品再 GET | checksum 不符、授权／TLS 错误、未固定输入 |
| 上传、导入、完整克隆、模板转换、启动、删除 | 原 UPID 状态及终态信息，允许的查询临时错误 | 明确任务失败；不可证明关联 |
| 克隆归属 | 原任务、source/target、候选 UUID、pool、完整 config/content 卷集合同步 | UUID／卷归属／明确非预期 pool 冲突 |
| 修改配置／扩盘 | 固定目标身份，预期配置、config 与存储容量同步 | 非法目标、身份变化、明确非同步性错误 |
| QGA／cloud-init／来宾事实 | 固定 VM/PID；启动、初始化、分区／文件系统增长、地址／路由／DNS收敛 | cloud-init 明确失败、明确错误身份或非法／冲突配置 |
| 删除后消失 | 已知成功删除任务，原 VM/UUID、完整卷集合，成功读取但旧对象仍在 | 替换对象、卷被其他对象持有、任务明确失败 |
| snippet | 原文件路径／digest／inode、helper 关联和完整引用范围；只读核验同步 | 内容／inode／归属冲突、其他引用、可见范围不足 |
| 常规 PVE 部署 verify | 原 saved plan、确定的 native 输出／state association、已绑定身份；配置／容量／旧对象消失 | expectation 不确定、身份／归属冲突；不重跑 provider apply |

依赖准备只覆盖既有锁定版本、来源及 checksum 可验证的网络传输，保留锁文件不变；不能借重试 `tofu init/apply` 来重放后端／设施操作。现有工具自身下载机制的边界单独声明。apt 软件包操作沿用其本身机制，失败仍使构建失败，本 change 不将 apt 命令包装成无限重试。

明确预期值尚未进入视图与确定的配置错误要区别：判定器依据原任务、阶段、字段类型和预期变化定义有限 pending 条件，不能把任意 mismatch 等到超时。采样先保存必要事实再判定，避免失去失败时的两个 `volid/vmid`。

### 4. 最少判定证据与原生停止诊断

证据按固定 `(phase, check, resource/task association)` 分组，各组保留最后一次必要观察和影响结论的状态变化：execution/request/runtime 绑定、UTC 查询时间、attempt、关联 UPID/PID／资源、expected/actual 安全字段、可控错误类别、原因及适用 cutoff。终止判定时冻结该检查的必要证据；后续 cleanup/source 或独立查询更新自己的组，不覆盖原 claim 的失败字段。全部已完成／失败检查的必要终态证据保留，不用一个全执行的 last-observation 槽。不记录每次完整响应；没有读取的字段标明未观察，异常不是空集合。

原生结果与可消费 CLI 摘要提供有 schema 的 `stop_diagnostics`，至少表达：

- 已完成阶段／子阶段、停止检查及 failed/unknown 原因；阶段完成不等于所有后续检查完成。
- 写派发事实和关联任务／PID，当前活动 running/stopped/unknown；附观察时间，旧 stopped 记录不能代替当前核验。
- 资源 registered-owned / candidate-unknown / not-owned 与 present/absent/unknown 分开，残留清单是否完整。
- 按检查保留的最后安全判定及失败证据，与恢复 supported、eligible/blocked/needs_evidence/not_applicable、原因和必要材料类别。

结果整体 unknown 可以同时包含已确定 failed 的任务／检查。缺终态或收集失败保持 pending/unknown；读取旧材料仅给已有事实，不能生成原执行成功或刷新时间预算。授权调用方不必解析私有日志。只允许明确列出的身份、卷所有者／容量、配置比较状态和受控原因；不输出 token、私有 URL、原始响应、cloud-init 内容或任意异常字符串。image 的内存拒绝使用其原生结构化结果；无需将本地重建任务纳入 PVE 恢复审批。

### 5. 登记前恢复：候选不是所有权

采用当前原生 clone 的 `description` 参数携带一次性关联标记。acceptance plan 生成 UUID 格式随机 nonce，构成固定 ASCII `iaas-acceptance-clone:<nonce>`，绑定 preview digest；admission 绑定该 preview，start 在原 journal 中持久化 marker、原执行身份／request／source／精确 target/pool/storage、完整空闲目标准入和 clone intent，随后仅在那一次 clone POST 携带 description。marker 不是凭据或授权，不能单独证明所有权；不提供调用方任意 description／marker 覆盖入口，不写源模板，也不额外 PUT 标记。

本次已只读核对 [Proxmox 官方 clone 参数文档](https://github.com/proxmox/pve-docs/blob/master/generated/qm.1-synopsis.adoc) 和 [qemu-server clone_vm 实现](https://git.proxmox.com/?p=qemu-server.git;a=blob;f=src/PVE/API2/Qemu.pm;hb=HEAD)：clone 接收 description，将它写入新配置，并为克隆生成 SMBIOS UUID。这里确定参数及持久化路径；这不是对目标设施的真实验收。

收到响应先记录 UPID；确认原任务 OK 后，在 pool／content 归属门禁前读取目标 config 的 marker、UUID 和挂载卷集合。marker 必须与原 preview/intent 完全匹配，UUID 必须有效且不同于 source，完整挂载槽位须符合冻结 source 的克隆预期，卷须在目标 storage 且不含 source 卷。保存这一完整候选配置快照（含 slot→volid）和采样时间；部分视图也保存必要字段，但标为 incomplete。候选始终不是 owned，只有 pool、content volid/vmid 等全部既有 claim 谓词通过才登记 `temporary_vm` 并允许正常自动 cleanup。

可恢复正例固定为：原 UPID 成功，完整候选配置快照已保存，但 pool／storage content 同步检查失败或到期，完整 ownership 未登记。recovery plan 验证不可变原材料中的 marker／clone POST／收到的 UPID、空闲目标准入及完整候选身份；再独立读取当前 config 和 content，要求 marker、UUID、完整 slot→volid 与原快照相同，pool／storage／各卷 vmid 符合原请求，源盘未混入，权限／引用可见且相关任务／helper 已停。此联合规则建立原任务到确切身份的关联；当前 VMID／name／pool、当前 marker 或任务成功单独都不足。

通过后新 preview 冻结候选快照中的完整 UUID／卷集合、原 exact snippet 列表和证明绑定，不从当前新挂载盘扩展原范围；start 使用新的有限批准，重核相同 marker、UUID、全套挂载／卷、引用／可见性／权限及原／后续活动。即使 UUID 或 marker 仍相同，卷新增／替换也拒绝；candidate 和 owned 状态始终分离。marker 支撑现有调用方串行操作与受保护证据模型，不作为抵御有权任意复制配置／改写证据者的密码学证明；已知并发替换或归属冲突立即拒绝，不建设新的全局审计系统。

上述当前 config／marker／UUID／挂载集合重查适用于 VM 存在时。若其后权威确认 VM 已不存在，start 或后续 limited recovery 不要求读取不存在的 config，但必须已有在 VM 存在时独立证明并冻结的完整 derived preview/proof scope；后续 recovery 还需绑定已提供的前次恢复材料和活动。依该范围与当前精确卷的归属／完整引用、可见性、权限、原任务／helper／已提供恢复任务的 inactivity 核验处理剩余项，不重发 VM 删除。不能仅凭 VM 不存在新建或扩大 derived scope；首次 pre-registration plan 缺少已独立证明的冻结范围且 VM 已不存在时仍 needs_evidence/unknown。当前 VMID 若被替换对象占用则走冲突拒绝，不能当作原 VM 已不存在而绕过身份门禁。

缺原 marker、可靠 UPID 或完整候选快照（包括 UUID／挂载槽位不全）的更早停止点返回 needs_evidence/unknown，当前合同不自动认领或删除；不能在 recovery 另写 marker、补写旧快照或靠现状组成原完整卷列表。原材料仅有旧无标记候选时也不补兼容路径。原始 journal/result 字节不修改，新证据和判定保存在新 recovery；恢复不克隆、configure/start 或 guest exec。

备选的按 VMID 认领或将候选直接写为 owned 都会在 VMID 复用／清单不完整时误删；强制编辑 journal 又损坏历史，均拒绝。既有已登记恢复仍保留完整清单、当前活动和引用检查，不因新增分支减弱。

### 6. 简单的执行器内存预检

build/test 客体启动前读取 Linux `/proc/meminfo` 的 MemAvailable，并在当前实际容器布局可直接读取时取其 memory limit/current usage。只比较已测宿主余量和当前容器有限 limit 减 usage 与本次 guest `memory_mib`；任一已知余量小于客体申请内存则拒绝并记录采样时间、请求值、测量值和 scope。不新增独立开销预算、资格阈值或公共策略参数，不要求扫描完整祖先层级或支持两代 cgroup 的资格矩阵。

读不到的 host/container 数据、非当前可识别布局或隐藏祖先限制，记录 unknown／原因与观察范围，单独不阻止客体启动；已知不足仍拒绝，未知不能冒充无限制或充足，也不因后续实际构建成功而补成 passed。预检不做资源预留，不保证后续无 OOM。离线声明检查与被动执行器观察分开，不能用规划机当前内存判定远端构建配置无效；模板 1 GiB／克隆 8 GiB 的目标资源配置保持原合同。

## Risks / Trade-offs

- 暂态分类过宽 → 每个 probe 显式 pending／retry allowlist，反例验证权限、冲突、非法响应立即停止；外部任务失败仅允许验收 DELETE 的严格存储插件兜底例外。
- 登记前关联材料可能不足 → 软件提供可证明路径和明确 blocked/needs_evidence；存在性不替代所有权，不强行通过恢复。
- 多个阶段消耗同一窗口 → 新合同明确截止绑定，局部 cap 只收紧；诊断展示剩余观察不足，而不续时。
- 内存观察存在盲点与竞争 → 记录采样及直接观察范围；已知不足拒绝，缺测量单独不阻断，未知不默认充足，不承诺保留资源。
- 共享组件扩大调用影响 → 定向 adapter 测试检查写计数、身份绑定和绝对截止；复用既有 transport/deadline，不改外部插件。

## 当前合同更新与验证范围

仅更新受影响的当前合同版本及其输入、schema、能力声明、示例和 infra-ops 适配清单；新 start 拒绝非当前合同，不提供旧版翻译。原历史材料只按已有保留证据规则读取，不重写、不新增兼容矩阵。离线 check、软件／替身验证、固定 OCI 版本发布、限定真实验收和调用方日常部署各自陈述；发布与真实设施步骤须在后续实施授权范围内完成。

软件实现为 A/B 范围；若另行授权 C 级真实验收，复用既有专用池和源模板，最多两个顺序临时 VM，覆盖正常主线及可证明的登记前停止／恢复。不得在共享 PVE 人为引发插件故障；临时错误用本地替身验证。维护成本为本组件与变化 adapter 的定向回归及既有发布流水线，真实复验仅在对应风险改变时触发。
