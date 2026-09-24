## Context

当前基线为 `7d0a038`（rc.12）。模板路径是 `build-template.sh` 经 SSH 调用节点 wrapper；wrapper 有本地 flock 和阶段日志，但没有可重连查询的执行记录。VM 路径已有 protected capture、S3 backend、二进制 plan 和 companion 绑定，目标元数据尚未包含实际 API endpoint，结果没有稳定的 PVE execution 关联。

本设计承接 [proposal](proposal.md) 的 IaaS 范围。当前 root 将 API token 作为普通变量、SSH 使用 agent 的站点问题通过新通用合同和合成示例交接，本站 root 文件不在本 change 中修改。

## Goals / Non-Goals

目标是让原计划执行、远端构建和失败材料可被调用方准确解释，且模板替换、管理归属冲突和未知 state 在写入前关闭。选用适合长时远端任务的机制，允许明确的版本切换和破坏性改造，不用兼容旁路降低准入强度。

IaaS 不成为发布登记或审批权威，不接收控制端秘密，不扫描所有 state 寻找全局所有权。当前软件交付依靠代表性回归和可销毁本地替身；真实设施验收、故障注入和发行操作需后续按授权安排。

## Decisions

### 1. 两个领域入口，共用 launcher 和公共阶段

新增 `pve-template` 组件，使用独立 recipe，不为了构建模板要求加载 VM 声明或 S3。它提供 `check/read/plan/apply/verify`：plan 的动作是 `build` 或 `cleanup`，apply 只执行选定预览；read 查询 execution 或观察明确模板，verify 核对记录与当前配置。在线 plan 不下载镜像到节点；校验 checksum 的实际下载在已授权 build 中完成，并报告缓存/工作文件副作用。

`pve` 保留 check/generate/preflight/health/prepare-dependencies，统一为 read/plan/apply/verify。plan 生成原生计划；apply 必须携带 `--plan`、`--companions` 和 `--execution-id`，没有直接 apply 或自动 replan 模式。read 观察所选 root 的 state 和明确对象；verify 仅按已存计划读取设备配置，不为配置检查隐式初始化 backend。read/plan/apply 访问 state 时才要求 S3。

不保留 `prepare-plan/apply-saved-plan` 别名；本仓库旧 Make/脚本写入入口迁到同一合同或明确报迁移错误，不能另行渲染后直接执行。保留已有纯只读/离线能力。OPNsense 的操作名称和结果结构作为公共一致性参考，PVE 不使用 OPNsense candidate 或 activation confirmation。

所有 VM/模板 apply 接收本次 `execution_admission`，绑定 plan/preview digest、target、execution ID，以及调用方已批准、持久化一次性消费预留和 pending、持有完整流程互斥的声明/引用。IaaS 在首个设施副作用前校验关联；调用方维护消费台账与跨 Runner 防重放，IaaS 不以新 execution ID 或 native stale-plan 检查代替该责任。人工核清可解除 pending，但不恢复原材料的执行授权；后续写入另行 plan、批准并预留。

### 2. 长时模板任务交给节点 systemd，helper 保持受限

扩展版本化节点 helper 协议：capabilities、预检/观察、提交构建、查询、执行清理。controller 通过 stdin 交接严格校验的 JSON 数据；不 source 调用方 shell、不接受任意命令、任意 root 文件路径或任意 unit 属性。

节点在短期 execution ID 提交锁下将请求和初始记录原子写入 root-owned `/var/lib/iaas/pve-template/executions/<execution-id>/`，再启动固定 worker 的 systemd transient service。unit 名由受限 ID 派生，禁用自动重启，worker 生命周期独立于 SSH。worker 在每个阶段前后保存状态、已确认对象、native task 关联（可取得时）和私有日志；日志不进入公共 journal/CI 输出。目录 0700、私有文件 0600，通过受限 helper 读取安全摘要或显式导出私有材料，不授予自动化用户任意 root shell。

worker 在首个缓存/设施副作用前另行取得现有节点构建 flock，并保持至变更阶段及终态记录完成；有界等待失败即返回未开始变更，取得锁后重新检查 VMID、空间和其他可变前提。cleanup 使用同一节点锁并在锁内复核原任务已停止和当前归属。短期提交锁不覆盖长时构建，读记录及同 ID 查询不等待构建锁，也不因提交 shell 退出而释放 worker 的锁。

先启动 unit 后才写记录会留下无法定位的远端任务，因此必须先持久化。提交 ID 已存在时同一请求只查询、不再次启动；请求不同则冲突。节点重启后不自动恢复执行；未完成记录且原 unit 不可确认时返回 unknown。query 结合记录、unit 状态和设备观察解释事实，不根据 PID 或对象存在推断成功。

runtime 正常轮询至终态；SSH 断开或 CI 取消只结束本地等待，不声称远端停止。受控终止由另行授权维护处理，cleanup 必须先确认 worker 和相关原生任务均停止。相比同步 SSH 加 trap，systemd 能可靠分离远端任务生命周期；相比自建队列/daemon，它复用节点已有服务管理机制。helper 安装包更新由本仓库交付，现场安装不自动执行。

### 3. 模板关联采用构建记录与原生对象身份，不做磁盘证明体系

模板描述记录包含 target、版本标签、build/observation ID、recipe/基础镜像来源、节点/VMID、SMBIOS UUID、磁盘 volume 引用和已核验关键配置。新建时使用新生成的 UUID；历史模板 read 返回明确的 `historical_observation`，只记录可观察事实，不补造清理或构建过程。

PVE 原生支持 SMBIOS UUID，创建/克隆流程会生成 UUID，因而可用于区别正常的删除重建；见 [PVE Qemu API 源码](https://github.com/proxmox/qemu-server/blob/master/src/PVE/API2/Qemu.pm)。它不是防管理员篡改的不可变认证：显式复制 UUID、磁盘引用或直接改盘超出此信任边界。所需身份字段缺失或受权限限制时返回 unsupported/unknown，不能退回仅比 VMID；补齐历史对象身份是另行授权的现场动作。

模板 build 不再接受 force，任何占用 VMID 都拒绝，清理和新建必须分别批准；这避免 helper 需要查询站点发布数据库来判断可否覆盖。禁止发布对象原地替换的策略由调用方维持，IaaS 负责不提供该覆盖路径和拒绝关联漂移。

VM plan 从原生 create/replace 动作提取实际 clone 依赖，在现有 companion summary 中固定对应描述记录。apply 使用调用方本次提交的 `template_admission`（绑定 plan digest、execution、目标、记录 ID、用途及当前可用/撤销结论），重新只读核对实际 UUID、volume 引用和关键配置；拒绝复用 plan 内的旧发布结论作为当前准入。该交接是受信任调用方的声明，不是 IaaS 自建签名或发布台账。

准入发生在 snippet 上传前；调用方保持覆盖模板生命周期写入和克隆的互斥。不依赖模板的已有完整克隆 VM 更新/删除不因模板撤销而失败；未知 clone 依赖不得猜测放行。临时验证用途可引用待发布记录，但必须显式标注用途、对象及授权，不能冒充已发布版本。

### 4. 清理遵循当前管理归属，验证 VM 使用原生 root

本 change 的克隆验证示例使用调用方提供的独立完整 OpenTofu root，通过正常 plan/apply 创建与删除临时 VM，来宾检查复用已有验证能力。无需增加一套 helper VM 克隆控制器。模板 helper 清理自身构建的未纳管 VM/磁盘；不负责清理 OpenTofu 管理对象。

cleanup preview 固定原 execution、对象身份和当前管理交接。调用方提供 owner 为 helper 或 OpenTofu 的受控记录及明确 state 关联；helper 创建证据不证明现在仍归其管理。OpenTofu 所有、已导入或归属未知时拒绝 helper 删除，由所属完整 root 生成新的删除计划。只允许清理已证实归属于原执行的 volume，孤立且归属无法确认的磁盘留待人工处理。

完整模板的删除按退役处理，另需调用方当前退役授权及依赖核清结论，绑定确切对象与 cleanup preview；发布或撤销状态本身不授权删除。尚未核清的依赖克隆阻断退役，已独立的完整克隆不算残留模板依赖。IaaS 不扫描全站发布台账，也不把完整模板当失败构建残留清理。

pending 期间恢复清理使用新的执行身份并带 `recovery_of` 指向原 execution。调用方单独批准、继续持有同域互斥和原 pending；IaaS 返回独立结果。只读 read/verify 不变成自动修复入口。设备删除但 state/声明仍不一致时，返回未核清事实，不提供自动 state rm/push/unlock。

### 5. VM root 和凭据合同直接升级

首期支持一个 PVE provider 目标和本仓库 VM 模块的资源类型；root 的 endpoint 使用固定非敏感输入，禁止第二 provider alias 或动态目标。通过原生 plan JSON 的 provider 配置引用与取值及选定 root 声明核对，不声称支持任意 HCL。未知 provider 配置形态在写入前拒绝。

采用 OpenTofu ephemeral 变量交接 provider API token、需要时的 SSH 私钥；固定 endpoint、TLS 设置和资源声明使用普通输入。保留受控 TF_VAR 名称通道，合成 root 将认证变量声明为 sensitive + ephemeral；不用轮换密码的 hash 作为身份绑定。参见 [OpenTofu ephemeral variables](https://opentofu.org/docs/language/values/variables/#ephemerality)。旧普通认证变量 root 明确拒绝，不做“也许 apply 会使用新环境”的兼容承诺。

SSH helper 使用显式 ssh_key/known_hosts。需要 provider SSH 时，从同一受保护输入映射 ephemeral 私钥及明确用户；不采用宿主 agent 隐式透传。API 用户和 SSH 用户可不同，build 与日常 VM 身份也可不同。plan/apply 各自 discovery 选择必要文件；未使用的 provider SSH 不成为强制依赖。cloud-init 在 plan 渲染一次，apply 不重新读取来宾密码变量。

固定 provider 的 [SSH 实现](https://raw.githubusercontent.com/bpg/terraform-provider-proxmox/v0.111.0/proxmox/ssh/client.go) 会接受未知 host，不能以挂载 known_hosts 或 OpenSSH 配置作为严格校验的充分条件。受支持 root 须显式给出可能使用的 provider `ssh.node` 地址/端口，覆盖原计划、state 和 clone 来源涉及的节点，禁止未解析目标回退到动态发现。runtime 在启动 provider 前验证这些实际目标均有可用可信条目，并将同一 trust 文件放到 provider 实际读取的位置；缺失/不匹配拒绝，不执行自动 keyscan 信任。受限 helper 自身仍严格校验主机。正常密钥轮换通过调用方当前可信文件交接，不把私钥或 host key 值当作计划配置身份。

首次 plan 前没有原生 plan，因此从受支持 root 的静态配置/声明和只读 state 提取所有可能节点及 clone 来源，核对固定地址映射与 trust 后才启动 provider；目标无法确定即拒绝。plan 生成后再用原生计划核对节点覆盖一致并绑定该节点集。apply 前消费已绑定目标并重验调用方当前 trust，不依赖先执行 provider 才发现缺失的 SSH 目标。

原生 JSON plan 全程私有。公共 review 采用允许字段投影：动作计数、受控对象显示 ID、unknown/破坏性影响和安全原因码；资源地址中的自由 key 不默认公开。replace 保留原生删除/创建顺序，unknown 更新不得归类为无中断更新。

companion 和 review 固定 `verification_requirements`：类别、范围、必需/可选、执行责任方或等价的固定策略引用；配置 verify 必需，来宾检查由调用方声明并执行。apply、独立 verify 和结果携带同一关联，不按执行后的最新策略降级。IaaS 不新增来宾检查引擎；必需外部检查无证据时明确 caller acceptance 未完成，独立 native success 可以保留。

### 6. State 准入与锁继续使用原生机制

调用方交接 `state_admission`：root/backend/workspace、`first_use` / `existing` / `reconciled_empty`、预期 lineage（已有时）及初始化/核清引用。IaaS 在任何可能初始化 workspace/state 的原生命令前，用只读 S3 GET 观察确切对象，按需 HEAD 辅助，返回 absent/present/error；仅明确的缺失对象响应可判 absent，拒绝访问、缺 bucket、传输或解析错误均阻断。不得用任意非零退出推导 absent，也不使用可能创建空 state 的 `tofu state pull`/StateMgr 作为观察器；固定版本行为见 [OpenTofu 1.12.6 S3 backend](https://raw.githubusercontent.com/opentofu/opentofu/v1.12.6/internal/backend/remote-state/s3/backend_state.go)。

观察器复用所选 backend 的 endpoint、region、path-style、TLS 和凭据配置，不另用 SDK 默认目标。key 规则与该版本一致：default workspace 使用 key，其他 workspace 使用规范化的 prefix/workspace/key。S3 服务端加密通过受支持 GET 权限读取；未支持的 OpenTofu 应用层加密或 state 格式明确 unsupported，不猜测解码或误报为空。读取不创建 state/lock，也不执行迁移。

first_use 只在已声明授权且目标 state 不存在或确认为空、计划所建对象无冲突时准入；existing 必须读取到预期 lineage；reconciled_empty 必须匹配交接的空 state 事实和原生身份（如有）。计划保留 admission 快照、原生初始化前后观察和可取得身份，apply 另交接当前 admission 并重读；允许同一次已授权初始化从 absent 变为关联一致的空 state，不机械比较枚举。原 first_use 不是既有 state 丢失后重新创建的永久授权。原生 plan 可能初始化空 state 或产生锁，此类 backend 效果须在 operation discovery/结果中区别于只读观察及 VM 写入。

既有 state 意外消失、不可读或归属冲突均阻断。旧 preflight 的名称/tags 只作 readiness 提示，不产生纳管授权；已确认由所选 state 管理的 VM 改名或配置漂移应进入原生计划，不能仅因声明不匹配就拒绝。未纳管的占用、对象身份冲突仍须先核清。

继续使用 S3 use_lockfile、backend/workspace 绑定、bucket versioning 前提和 native stale-plan 检查。预读 serial 不替代原生 apply 锁内校验；不承诺消除 snippet 上传后才发生的 stale-plan 拒绝。调用方锁覆盖整个设施写入窗口，本仓库不新增跨 Runner 锁。

### 7. 结果保留事实维度，verify 不伪造历史

增加带版本的 PVE result，字段包括 target、plan/preview digest、execution_id、runtime、state 关联、phase、effects、native_execution、state_persistence、verification、collection 和 recovery 引用。设施副作用独立为 none/known/unknown；SSH 上传部分失败也不能报 none。state_persistence 使用原生写回结果：完整捕获的 native apply 正常成功退出且无写回错误，作为原生持久化确认；不另建逐对象持久化证明。执行中断或缺证据是 unknown，不以事后 state 相同反推成功。

VM 成功要求 native apply 完成、原生持久化确认且必需配置 verify 通过、必要材料完整；调用方归档失败不会改写这一原生结果，由调用方保留 pending。模板构建成功表示配置已核验、材料完整，发布可用性单独表达。未运行的来宾/业务检查保留 not_attempted/not_performed；本期正式配置验收不强制接管独立来宾检查的策略。

配置 verify 使用原计划的动作/期望，不读最新声明替换范围。对变更 VM 核对 VMID/node、存在或删除、CPU/内存、磁盘大小/存储/附着、NIC/bridge/MAC、cloud-init 引用、期望启动状态；有声明的 passthrough/HA 属性使用现有可表达检查，否则计划明确 unsupported。未知字段在 apply 后用确定的原生结果补足，无法验证的必需项保持 unknown。删除依据计划 before 保留的身份，读取权限不足不能当不存在。无 VM 动作时明确配置验证范围为空，不宣传整集群核验。

替换由 before/after 身份及原生动作顺序归一成最终期望：同 VMID 重建检查新对象关联和配置，不再要求该 VMID 缺失；不同 VMID 或 create-before-destroy 还需核对旧对象退出，不能遗漏旧/deposed 实例。当前配置相符与原替换动作完成仍是两个结论。

原 apply 在调用方串行窗口内收集受保护的执行后原生 state/资源结果快照及确定期望，关联 plan、execution、backend 和可取得 lineage/serial，不要求任意 root 转发模块 outputs。采用上述只读观察路径，不为取材料重新初始化缺失 state。独立 verify 消费原计划和这份关联材料，不隐式访问 backend；若材料缺失或仍未知就保持 unknown，不能读取当前设备再把其值当期望。稍后 read 的 state 只是现状观察，不能补造原执行成功；收集失败保留 native 结果并报告 collection 未完成。

输出收集或原生持久化失败保留原 capture、errored state、节点执行记录和唯一容器存储；controller 被强杀允许无终态，由调用方保持 unknown。read/verify 提供事实供补登记/人工核清，不能写 `manually_reconciled` 冒充本仓库原执行成功；该台账状态由调用方决定。

### 8. 版本切换和交付选择

新 PVE saved-plan metadata 使用 v2；模板 preview/receipt 与 PVE result 各自 v1，launcher discovery 公布组件合同和 helper 协议版本。旧 PVE metadata v1、旧 helper 或不具备所需操作的 launcher/runtime 组合明确拒绝。OPNsense v3 candidate 不变；不为本次改造建立跨组件万能 candidate。

软件验证覆盖身份、断线、凭据、state、删除和收集失败的代表性正反例，复用本地 Docker/DinD 传输测试与合成 state 服务。节点 systemd 行为通过受控本地服务管理替身和可用的可销毁 Linux 环境验证；PVE 行为以模拟 API/命令合同验证并明确其证据边界。不得为了完成软件交付自动接入真实 PVE。

## Risks / Trade-offs

- 远端 worker 与 controller 生命周期分离 → 取消等待后节点可能继续构建，结果明确 running/unknown；调用方不得释放互斥并立即清理。
- 原生 UUID/volume 引用可被管理员复制 → 对受支持路径和正常删除重建有效，不提供磁盘防篡改证明；异常记录重新核清。
- 发布有效性与 state 准入来自受信任调用方 → IaaS 校验绑定与实际对象，调用方负责当前台账、批准及串行化，不能用历史材料自我批准。
- 硬切换增加调用方适配成本 → 提供明确拒绝、版本表和迁移示例，避免维护两条语义不同的写入路径。
- snippet 仍可能在 native stale-plan 拒绝前写入 → 保留逐阶段事实及恢复材料；不可变 snippets 后置，不能把空资源 diff 宣称为无副作用。

## Migration Plan

1. 在实现分支完成新合同、helper 安装资产、launcher 和合成示例；旧保存材料只保留，不修改内容升级。
2. 软件检查通过后交付版本/兼容说明及构建产物；实际 tag/镜像发布按后续授权执行，不在本次 spec 编写中触发。
3. 调用方在独立维护窗口部署新版 helper、改写 root 认证声明、完成 state 初始化及模板历史登记，再重新 plan。上述现场步骤不进入本仓库实施任务。
4. 回退不能通过旧入口消费新材料，也不能靠旧 force 或旧计划重放；保留原执行和恢复材料，由维护者先核清设施/state，再选择兼容版本重新规划。
