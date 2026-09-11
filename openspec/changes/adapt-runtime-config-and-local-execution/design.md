## Context

需求与范围见 [proposal](proposal.md) 和 [需求清单](../../../docs/iaas-runtime-adaptation-requirements.md)。规划创建于 `main`，实现位于 `feat/adapt-runtime-config-and-local-execution`；当前接口及实际验证边界见[启动器指南](../../../docs/runtime-launcher.md)和[验收记录](../../../docs/runtime-adaptation-validation.md)。

创建设计时的源码基线（保留的旧入口仍遵守这些契约）：

| 当前入口 | 本设计的约束 |
| --- | --- |
| Makefile 从 `ENVIRONMENT_DIR/inventory` 和 `ansible/` 取默认输入 | 新适配层解析配置并提供显式组件输入，兼容现有显式入口 |
| `runtime_paths.validate_paths` 默认保护固定目录 | 将已解析源文件及显式外部输入统一纳入保护，不能只沿用旧目录清单 |
| `pve-plan` 未保存原生计划；`pve-apply` 重新渲染后上传/验证，再调用 `tofu apply -var-file` | 新增独立保存计划路径，不能把当前 apply 直接包装成应用已审阅计划 |
| cloud-init manifest 已有 tfvars 与 snippets SHA256；上传/验证消费现有字节 | 复用这些绑定，不新增逐文件证据框架，不重新生成已保存的密码 hash |
| 镜像构建固定 Linux amd64；provider 初始化单独允许网络 | Mac 首轮显式 amd64 模拟，原生 arm64 按实际工具/provider 能力声明 |
| 现行本地 state 备份 helper 只复制 root 下的文件 | 不把该 helper 成功当成 S3 备份，写回失败恢复走单独输出生命周期 |

GitNexus 用于查找及复核 cloud-init 调用流程。新入口在缓存图中为 UNKNOWN，实施时结合当前源码调用与定向回归核对；已有 artifact loader 的 impact 为 LOW。各阶段提交前执行 graph change analysis，不以空调用集合替代验证。

## Goals / Non-Goals

目标是把已确认的 35 条需求转成可实施的配置、调用和生命周期契约，保持领域逻辑及现有权限保护。最低运行依赖为一个安装好的启动器与 Docker CLI/可达 engine；设施工具链留在镜像内。

不构建通用配置平台、动态插件系统、审批系统、跨机器执行锁、不可变 snippets 或垃圾回收。不开通或迁移调用方真实 S3，不资格化真实 PVE/K3s，不承诺原生 arm64 完整能力；合成测试不提升为真实设施验收。

## Decisions

### 1. 配置编译后复用现有组件模型

入口采用带 `schema_version: 1` 的 YAML，包含逻辑环境标识、共享 facts 文件、组件输入映射及具名场景。组件输入按 OPNsense、switch、PVE、services、foundation、K3s 等现有职责组织；生成的 Ansible inventory/vars 仍可使用运行时内部布局，但调用方无需维护该布局。

每个场景完整指定需要变化的组件输入映射；选中场景替换对应组件映射，不做递归 merge 或多层继承。不指定场景使用明确的日常默认输入；未知场景失败，不回退。未选场景不做领域解析、生成或执行。

引用使用独占节点，例如 `{ $ref: "facts.networks.management.cidr" }`，只允许命名共享事实及其字段路径，不做字符串插值、脚本、环境变量展开或模板求值。允许事实之间引用，检测所选输入可达引用的缺失、类型错误和循环。解析后送入现有 schema/invariant 校验。共享事实与策略字段可分别声明，不因值相同自动合并。需要跨组件事实时只读所需事实，不执行依赖组件。

只校验/生成一个组件时，仅要求其必要输入。对在线 scope 使用现有领域限制：不默认 all，不通过裁剪同一 OpenTofu root 的 VM 声明来伪造安全的局部 apply；需要完整 root/集群时要求调用方显式选择该完整范围。

采用有限显式引用而非 CMDB/模板继承，是为了消除重复事实而不改变领域规则。配置入口的完整字段 schema、示例及代表性错误样本在任务 1 中一起实现；上述解析和选择语义已确定。

### 2. 源路径与任务输出分离

配置内相对路径以声明文件目录为基准；命令行路径以客户端调用目录为基准，启动时转为明确位置。符号链接解析后的真实路径参与输入/输出冲突检查。外部输入必须显式声明；不能把不可见的客户端路径原样当作 daemon 路径。错误只报告必要的逻辑字段和路径，不回显秘密值。

启动器为每次运行分配独立任务目录。输入按声明关系只读提供；生成物、审阅内容、计划、恢复输出与临时文件分类保存。显式导出只复制被选择的非敏感生成物，不覆盖手写配置。普通输出可由调用 UID/GID 读取清理，敏感目录/文件使用 0700/0600，保留现有受保护文件 owner/mode 及 SSH known_hosts 校验。

输出摘要使用逻辑来源、所选场景、Git revision（如存在）、镜像 digest 和标准报告。无 Git 元数据或有未提交修改时如实注明，不将单个 revision 宣称为全部输入字节证明。已有 cloud-init 校验保留，普通配置不新增逐对象 hash 门禁。

### 3. 轻量启动器和运行时共同接口

新增一个独立发布的原生 CLI 启动器，采用 Go 构建以避免宿主 Python/Ansible/OpenTofu 依赖；Go 和其锁定依赖只参与启动器构建，不进入设施运行镜像。安装提供 Linux amd64 与 Darwin arm64 二进制及标准 checksum；升级由用户显式选择版本，不运行时自动更新。

启动器只负责版本自举、声明文件定位与传输、Docker 生命周期和产物回收；领域 schema、引用求值和操作分发在镜像内 Python 实现，使用现有 uv 管理环境。启动器仅做定位文件所需的结构读取，不维护第二套领域校验器。

调用方显式传入环境入口和独立的运行时选择文件；后者至少含接口版本、image reference、platform，本地/CI 共用一份。独立选择文件避免“必须先运行镜像才知道选哪个镜像”的循环。禁止隐式 latest；固定发布 tag 在准备阶段解析成 digest，保存计划一律记录并使用确定 digest。安装好的启动器与已准备镜像能够执行纯离线检查，不为解析 tag 强制查询 registry。

启动器接口主版本、配置 schema 版本和镜像能力元数据执行简单兼容检查。未知组合在生成或设施访问前失败，不自动换版本。元数据包含受支持操作/架构；只读发现不能访问设施或秘密。采用静态操作表，不透传任意 Makefile/脚本以绕过分级。

规划命令形态为 `iaas run --environment <file> --runtime-config <file> --engine local|dind --component <name> --operation <name> ...`；具体旗标拼写可在实现时统一，但环境、版本、模式、组件、范围、计划与输出选择必须显式且无歧义。

### 4. 本地挂载与 DinD 文件传输

`local` 仅在客户端路径确实对 daemon 可见时使用只读 bind mount。`dind` 不依赖宿主 bind 路径：启动器经 Docker API/CLI 将声明输入上传到任务自有卷，再启动执行容器；配置依赖发现可迭代请求显式引用文件，传输不隐式读取无关目录或未选场景文件。转换后的逻辑挂载映射供容器内解析器复核，非秘密输入与受保护文件分开传递。

DinD 在任务卷内按执行 UID 设置 owner/mode；受保护文件只读呈现给执行进程。需要控制流程的临时容器仅用于任务卷准备/复制，不能放宽设施操作用户或秘密读取权限。docker socket 不挂入设施运行容器。

正常完成：取得真实退出状态、回收所选结果，再清理任务自有容器/卷。取消先请求进程正常退出并等待明确结果；升级终止须报告中断状态，不能包装为成功。在线任务不使用无条件 `--rm`，回收失败或发现唯一恢复副本时保留容器/卷并给出受保护恢复位置。无法防止用户或外部 CI 强制销毁 daemon；该事实是当前环境边界，不新增独立恢复服务。

相较要求 DinD 和客户端共享同一宿主目录，显式传输更符合现有运行方式。代表性真实 DinD 验证需事先确定 daemon/卷生命周期和授权范围，不能仅凭本地 bind 测试完成验收。

### 5. 操作分级与凭据

| 类别 | 网络/state | 输出与保证 |
| --- | --- | --- |
| check | 镜像准备后禁网，无 S3/设施凭据 | 语法、schema、可达引用、关键不变量与组合检查 |
| generate | 禁网，无设施凭据 | 仅所选非敏感派生配置，输入不变；不包含凭据化 cloud-init 最终渲染 |
| prepare-dependencies | 显式允许下载；backend-disabled | 锁定 provider/module 准备，不更新 caller 锁文件，不声称设备兼容 |
| diagnose | 按组件联网；只有读取 state 的操作要求 S3 | 设备只读诊断可能写本地报告，不宣称等同 plan |
| plan / prepare-plan | S3 初始化及读取/锁、设施只读；按需注入秘密 | 生成原生计划和受保护配套 snippets，不上传设备 |
| apply-saved-plan | S3 锁/state 写回、设施写入 | 应用指定计划；前置上传可能早于 state 过期拒绝 |

命令帮助及结果同时列出联网、state 访问、设施写入和本地写入。未支持的组件/操作组合直接报错；不为所有组件制造 plan。新入口仅显式支持的既有操作及保存计划，不隐式开放 destroy/template-build 等命令；既有低层入口仍保留各自显式授权语义。

首轮新入口的组件支持范围如下；表中名称表示操作语义，最终命令拼写由共享分发实现确定。所有组件支持所选输入的离线 check；generate 仅导出已有领域格式的非敏感派生输入或报告，不凭空增加领域生成能力。

| 组件 | 首轮必须接入的组件操作 | 新入口范围之外 |
| --- | --- | --- |
| OPNsense | 现有 vars 校验、diagnostics 只读诊断 | 配置写入 playbooks |
| switch | 所选配置检查、readonly-facts 只读采集 | config-plan 及配置应用 |
| PVE | 现有配置生成/检查、API preflight/health、prepare-dependencies、plan/prepare-plan、apply-saved-plan | destroy、模板构建、直接 apply 与 guest bootstrap 保留既有独立入口 |
| services / foundation | 现有配置生成/检查；foundation health | 不新增通用 plan/apply |
| K3s | 现有 check/render、preflight/verify、显式 deploy/snapshot/upgrade | platform-handoff 保留既有独立入口；不提供 OpenTofu 式保存计划 |

K3s deploy/snapshot/upgrade 归为显式设施变更，保留其现有凭据、范围及前置条件；snapshot 会写远程备份，不能归为只读诊断。以上在线操作不因新入口存在而默认执行。表外入口保持原有用法，不由新入口任意透传。

设施和 S3 凭据由调用方分别注入，按操作 allowlist 传入；不传递整份宿主环境、OP token 或桌面会话。调用方环境值/凭据不进入 runtime repo 或镜像。最终 cloud-init 渲染会消费用户材料，属于受保护计划准备，不能混入无秘密 generate；上传/应用消费已保存字节，不再次取得密码以重新渲染。

### 6. S3 状态与恢复生命周期

新入口中所有访问 OpenTofu state 的操作只接入调用方声明的 S3 backend。配置由调用方 root/backend 配置及注入参数组成，选择同一 endpoint、region、bucket、实际 workspace key 和 workspace；同 root 不因本地/CI 生成不同 key。非默认 workspace 的 key prefix 也属于状态位置，必须一致。

bucket 和版本控制由调用方预先准备；运行时不创建 bucket，不自动迁移 state。缺少配置、backend 初始化失败或锁不可用时停止，不静默使用空本地 root。使用 `use_lockfile=true`，有限等待/失败，不加第二把分布式锁，不自动 force-unlock。临时 root 内保存工作配置和 backend 初始化缓存，不把临时存储当作 state 后端。

S3 初始化不是所有在线操作的前置条件；独立 OPNsense/switch/K3s 诊断和不读取 state 的 PVE API 检查不需要 S3。原有明确使用 local backend 的低层调用不由本变更迁移；文档将其标为旧入口行为，不代表新入口支持本地回退。

写回失败后产生的恢复 state 必须以 0600 保存在独立恢复输出；本地模式优先直接落入保留目录，DinD 先确保卷仍存活再回收。正常输出和恢复输出的收集不能抹掉执行失败。恢复位置回收失败则保留唯一副本及其资源；报告失败步骤和位置，不打印原始 state。禁止自动 state push、覆盖远程状态或重试 apply。文档只提供调用方人工处理入口，实际恢复另行授权。

远程写回与本地恢复文件写入同时失败时，OpenTofu 可能将完整 state 紧急输出到进程输出流。因此，state 变更子进程启动前必须在容器内准备受保护的 stdout/stderr 捕获通道，原始流不得直连或 tee 到容器日志、终端、CI 日志。公共输出仅由受控阶段/状态摘要生成，不依赖事后按敏感词过滤。捕获文件按 0600 恢复材料保留，可能包含 state 的紧急输出不作为普通日志导出，也不自动推送远程 state。捕获无法准备时在变更前失败；运行中捕获失败时不得回退公开原始流，保留已捕获内容和可用存储，报告原操作结果、捕获失败及“恢复材料完整性未确认”，不能声称已成功保留恢复 state。无需另建恢复服务或签名系统。

### 7. 原生计划及串行执行边界

保存计划产物包括原生 plan、受保护审阅内容、provider lock、计划使用的输入/必要 root 文件、原样 snippets 与现有 manifest，以及一个简明运行摘要。摘要记录环境/root/backend/workspace、场景/完整范围、输入来源、镜像 digest；它用于防止误选，不作为额外证明系统。root 内相对文件依赖必须随产物可重定位，镜像模块仍位于固定 `/opt/iaas` 路径。

在原生计划成功生成后，配套 manifest 增加该计划文件的 `plan_sha256`，与原有 source tfvars/snippets 摘要一起保存和传递。应用时先将所选原生 plan 的 SHA256 与配套 manifest 记录值比较，再执行既有输入/snippets 校验；缺少或不匹配在任何 SSH 写入前失败，不能在应用时补写或重新绑定期望值。该单一绑定防止同一 root/state 下计划 A 与配套产物 B 的误混用，不提供对可同时篡改所有产物的攻击者的真实性保证，不增加逐对象证据系统。

计划由 `tofu plan -out` 产生；计划准备先完成 current-input 校验及凭据化 snippets 渲染，再保存原生计划。只在全部必需产物齐全后报告可应用计划，失败的半成品不能作为成功结果。provider 下载独立准备，实际 backend 初始化和 state 锁按 plan 的在线边界执行。

应用前在固定 digest 下核对目标、版本、锁文件、授权选择与配套输入；所有静态检查及必要凭据/backend 准备在 SSH 写入前完成。应用路径读取计划产物中的 tfvars，复用 manifest 校验，不与当前任意工作树混合、不重新渲染、不传新 var-file 改写计划。计划的旧配置快照可以在调用方明确授权该计划时使用；要求更新配置时必须重新规划，而不是自动混合。

完整顺序为：静态/目标检查 → 已保存 snippets 校验 → 上传 → 远程验证 → `tofu apply <plan>` 原生获锁/过期检查/执行 → 保留结果与恢复产物。旧直接执行路径的 current-input 和 rendering 顺序仍保留；保存计划路径是其明确例外，不削弱 standalone upload 的来源校验。

调用方单任务 CI 串行覆盖整个写入流程，本地变更避免与其他变更重叠；本地 check/generate/plan 可独立运行，plan 仍遵守 state 锁。无需实现 launcher 层共享锁。过期计划可能在上传并覆盖 snippets 后被拒绝，报告已完成前置步骤，不声称零副作用或自动回滚。任何 apply 失败都需调用方检查实际结果后重新规划授权；已知绕过 OpenTofu 的设备修改也应触发重新规划，原生 state 检查不等于实时设备漂移证明。

不可变文件发布和覆盖全流程的锁是后期备选，见 [路线图](../../../docs/roadmap.md#deferred-pve-concurrency-protection-beyond-serial-execution)，不生成本轮实施任务。

### 8. 兼容、平台与最小验收

现有 ENVIRONMENT_DIR/OUTPUT_DIR/显式文件命令保留；新入口只接受 schema v1，缺版本/不支持版本报告迁移错误。迁移文档展示手工增加入口与运行时选择文件、引用旧输入的方法，不自动改变源文件、资源地址或 state。删除旧目录接口不在本轮范围。

Linux amd64 为完整基线；镜像构建也支持显式 `RUNTIME_PLATFORM=linux/arm64`，两个架构的工具下载均固定校验值，CI 使用各架构原生 runner 串行构建与验证。Mac arm64 宿主安装原生启动器，可选择 arm64 镜像或显式 amd64 模拟。镜像报告实际架构，启动器按调用者选择校验；保存计划绑定运行架构，跨架构及缺少架构字段的旧计划需重新准备。provider 及真实设施能力按实际证据声明，不能静默模拟。Release 在两个架构串行构建与验证通过后，分别保存已测试镜像并核对来源和架构身份；发布任务只加载这些产物，先发布版本架构标签，再按不可变 digest 生成包含 amd64/arm64 的同一版本 manifest。已有标签不得覆盖，仅相同产物可重试或续发；完整重建导致身份变化时使用新版本。两个原生 runner 分别验证共享 manifest digest 的匿名拉取与能力查询。历史单架构标签不改写，Linux arm64 启动器产物不在本扩展内。

测试分组复用路径、cloud-init artifacts、PVE lifecycle、K3s、容器 smoke 的现有 fixtures；新增仅覆盖新配置/选择语义、传输、恢复及保存计划关键正反例。公共 CI 不连接设施，独立准备阶段可下载锁定依赖。真实 Docker/Mac/DinD/S3 验证在确定可销毁环境及授权后进行，未完成不标为已验收；不执行真实设施 apply 来验证本设计。

## Risks / Trade-offs

- 固定 snippets 名称可能在计划拒绝前被覆盖 → 当前接受已记录边界并依赖调用方串行，不扩大本轮方案。
- DinD 产物只留在可销毁 daemon 上 → 回收先于清理，保留失败不删唯一副本；外部强制销毁不属于软件可保证范围。
- 原生 launcher 增加一项构建工具链 → 仅构建阶段使用，运行镜像保持当前工具栈；复用标准依赖锁和 checksum。
- S3 兼容服务不一定具备所需条件写入 → 在所选服务的限定测试环境做代表性读写/锁竞争验证，不扩大产品矩阵。
- 多入口和新格式可能导致误混用 → 显式格式和版本选择、冲突时报错、逐组件迁移示例。

## Migration Plan

1. 授权实施时先确认实现分支及工作树处理方式；本次不创建或切换分支。
2. 完成配置/生命周期契约、启动器和镜像接口后，更新通用操作手册及合成迁移示例；原有命令继续可用。
3. 调用方单独审查实际入口、版本选择和 S3 配置；既有 local state 迁移必须另行授权，不能在试跑新入口时发生。
4. 软件通过后按独立授权完成平台/执行方式验收；发布沿用显式 release 流程，不自动创建 release。
5. 回退只选择兼容的旧启动器/镜像及旧配置入口；不回滚设施或迁移 state。不可将新计划交给旧镜像应用。

## Requirement coverage

| 输入需求 | 本 change 的合同及实施组 |
| --- | --- |
| ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07, ENV-08 | runtime-environment-config；任务 1 |
| RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, RUN-07, RUN-08 | runtime-launcher、oci-runtime-delivery；任务 3、5 |
| OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06 | runtime-launcher、runtime-environment-config；任务 1、3 |
| OPS-07, OPS-08 | runtime-saved-plan-execution、pve-automation-foundation；任务 4 |
| DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07 | runtime-launcher、pve-state-and-secret-operations、runtime-saved-plan-execution；任务 2、3、4 |
| DIST-01, DIST-02, DIST-03, DIST-04 | oci-runtime-delivery；任务 5、6 |
