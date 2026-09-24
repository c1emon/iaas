## 1. 合同与入口

- [x] 1.1 实施前确认并按仓库规则进入 change 对应实现分支，检查工作树；以分支及状态记录验证，不自动处理其他未提交修改。
- [x] 1.2 定义 PVE v2 plan metadata、v1 result、模板 v1 preview/receipt、execution/state/template admission、固定 verification_requirements 和 recovery_of 校验模型；用缺字段、旧版本、目标/执行身份冲突、缺消费/pending 关联及验收要求事后降级的代表性测试验证。
- [x] 1.3 增加 pve-template recipe 选择及独立 check/read/plan/apply/verify discovery；用不加载 VM/S3、拒绝无关凭据和未声明文件的测试验证。
- [x] 1.4 将 PVE 正式操作统一为 read/plan/apply/verify，扩展 launcher execution ID；移除旧 prepare-plan/apply-saved-plan 和无准入直写旁路，以 CLI 拒绝/完整交接测试验证，保留其他组件回归。

## 2. 模板远端执行

- [x] 2.1 扩展节点 helper 版本、严格 JSON 数据入口与能力查询，交付受限 sudo/安装资产；用恶意路径/命令参数拒绝测试、shell/Ansible 静态检查验证，不安装真实节点。
- [x] 2.2 实现先持久记录再提交 systemd transient worker、固定 worker 参数、私有日志，区分短期提交锁和 worker 全程节点锁；用提交中断、同 ID 查询、ID 冲突、不同 ID 并发及 cleanup 竞争、锁后重检、连接断开与禁用自动重启的服务管理替身测试验证。
- [x] 2.3 将现有镜像校验、customize/sysprep、创建/导入/转换步骤接入阶段记录，移除 force 和忽略必需清理失败的路径；用 checksum/VMID/helper/存储前提失败及阶段故障测试验证。
- [x] 2.4 实现 execution 查询及有界轮询，保留远端 running/unknown、节点重启和未完成 receipt 的真实语义；用断线重连、不自动重放和失去终态证据的测试验证。
- [x] 2.5 实现模板配置 verify、SMBIOS UUID/磁盘引用关联、历史观察记录和 private export；用新建与历史模板、缺身份、同 VMID 重建及缺清理证据场景验证。
- [x] 2.6 实现 cleanup preview/apply、原 execution/recovery_of 关联、停止与当前管理归属检查；用失败构建精确清理、仍在运行、归属未知、已导入 state 和发布退役约束测试验证。

## 3. VM 目标、凭据和 state 准入

- [x] 3.1 定义受支持的单 PVE provider root 合同并核对 plan JSON 中实际 endpoint/TLS 与固定 target；用 SSH 相同但 API 不同、多 provider/动态目标拒绝测试验证。
- [x] 3.2 提供采用 ephemeral 认证变量的合成 root 和受控环境/文件映射，provider/helper 显式 SSH 可用且不依赖宿主 agent；首次 plan 前从静态声明/state 确定 SSH 目标、plan 后绑定并在 apply 前重验 trust，用无已有 plan 的首次规划、非默认端口、缺 host 信任/未知节点拒绝、错误 key、plan 后更新凭据仍消费原计划、旧普通认证变量 root 拒绝和日志脱敏测试验证。
- [x] 3.3 实现只读 S3 对象观察、first_use/existing/reconciled_empty 准入及初始化前后 lineage 关联；用 default/非 default workspace 路径与 backend 目标一致、缺对象/缺 bucket/拒绝访问区分、未支持加密拒绝、观察无 state/lock 写入、意外缺失/身份变化拒绝、首次初始化产生相符空 state 及资源冲突场景验证。
- [x] 3.4 修正 preflight 名称/tags 仅表示声明匹配的报告，不将其作为 root/state 纳管证据；用已纳管 VM 改名/配置漂移仍可规划的正例，以及标记相同但不属于所选 state 的反例验证，保留只读检查范围。
- [x] 3.5 从私有原生 plan 生成安全机器摘要和确定的 clone 依赖，将模板记录与新 metadata 绑定；用 create/update/delete/replace/no-op、unknown、替换顺序和敏感资源 key 测试验证。
- [x] 3.6 在首个设施副作用前核对当前 template admission 和实际对象，保持调用方串行化交接；用撤销、缺当前准入、同 VMID 重建、待发布验证用途及无模板依赖的更新/删除测试验证。

## 4. 执行结果与核验

- [x] 4.1 为 PVE 执行持久化绑定结果并独立记录阶段、副作用、native apply、state 写回及 collection；用部分 snippet 上传、空 diff 上传、native stale-plan 和 state 写回失败测试验证，禁止自动 retry/push/unlock。
- [x] 4.2 实现原计划关联的只读配置 verify 和执行后私有 state/资源结果快照，覆盖关键配置、删除及同/异 VMID 替换的最终期望；用未转发 root outputs、缺原始快照、期望停止、旧/deposed 对象残留、权限不足、未知必需字段、空范围和必需来宾证据缺失测试验证，禁止以当前设备自设期望。
- [x] 4.3 提供只读结果关联/恢复观察，完整原材料可供补登记，缺结果时不反推历史成功；用原结果不变、设备/state 不一致、关联冲突、read/verify 无写入及人工核清不恢复旧计划消费资格的合同测试验证。
- [x] 4.4 保留私有 capture、errored state、远端 receipt 和导出失败后的唯一存储；用现有恢复测试与 controller 无最终结果、结果收集失败场景验证，不将任务失败改写为成功。

## 5. 软件集成与交接

- [x] 5.1 验证本地 Docker 与 DinD 的操作发现、文件传输、权限、执行身份和结果保留一致性，复用现有 runner/合成 backend 测试；报告替身和实际容器覆盖差异，不接入真实 PVE。
- [x] 5.2 提供模板 build/观察/清理与 VM plan/apply/verify 的合成调用示例，以及独立验证 root 的创建/删除材料；验证示例 schema、命令参数和离线生成，不执行设施写入。
- [x] 5.3 更新 runtime、PVE 操作与 helper cutover 文档，列明 API/SSH 权限、systemd 前提、旧接口/旧计划拒绝和调用方责任；用文档链接及示例一致性检查验证，明确未做现场验收。
- [x] 5.4 运行与实际修改相符的 Python/Go/Ansible/shell 检查及现有 PVE/OPNsense runtime 回归、OpenSpec strict 校验；汇总覆盖和限制，按仓库要求在提交前完成 GitNexus 变更分析。
- [x] 5.5 更新本仓库发行兼容说明和构建检查，验证 launcher/runtime/helper 版本发现及产物完整；实际 tag/镜像发布另按授权执行，infra-ops adapter、现场安装/state 迁移和实机验收不作为本任务执行项。

## 实施验证边界

- 初次实施已实际构建本地 Linux ARM64 runtime，并通过容器 smoke、操作发现、离线模板 check、SDK 导入和镜像内容检查；launcher 的 Linux amd64 / Darwin arm64 构建通过。
- 复核修复补齐 launcher 与真实 Python discovery 的接合测试、native plan JSON 传输、固定模板 helper、receipt 历史读取、state 对象关联和创建 VM 前失败清理；相关验证为本机软件与节点命令替身，不替代新版镜像或现场验收。
- 上游语义复核修正 VM 缺失判断、目录型卷 ID 和存储预检：以目标 VMID 的有效读取权限及清单确认缺失，构建/清理覆盖目录卷，并在变更前检查 datastore 能力、状态和 cache/work 文件系统空间。
- S3 使用真实 boto3 对本地合成 HTTP 服务验证；PVE API、SSH、systemd/节点命令和 DinD 编排采用代表性替身。未进行共享 CI 或 PVE 实机资格验收。
- 未安装节点、写入真实设施、迁移 state、执行来宾/业务验收或发布 tag/镜像。原执行事实与当前配置核验保持独立。
