# 软件验收与消费交接

日期：2026-09-19。实现分支：`add-opnsense-config-workflow`。
范围：通用工作流的软件实现与合成响应验证；未访问真实 OPNsense、未发布镜像、
未接入消费仓库、未执行现场写入或业务验收。

## 实现与结果

七类标准资源接入 read / plan / apply / verify。候选保存完整声明、固定执行集合、
连接身份、runtime digest/架构、来源及相关现场快照；apply 只使用审查后的候选。
已有身份需明确 managed/adopt；删除必须显式 absent，普通 no-change 不保存或 reload。
必要正反引用用于安排创建、切换、退役；写前和每阶段检查相关漂移及共享激活准入。
保存、激活、配置核对和活动核对分开记录，失败停止依赖阶段，不重试或自动回滚。

写前 recovery 保存实际旧值与不存在标记。旧规则缺少重新创建所需的声明安全上下文，
或原生字段不能无损表达时，标记 manual_required。未知后态、后续漂移及未尝试对象
不能直接自动恢复；可表达且已核清的材料通过 plan 产生新反向候选，再显式 apply。
调用方可以先核清材料；本实现没有自动修复未知恢复结果的旁路。

## 软件证据

- OPNsense 与 runtime Python/Ansible 回归：503 passed。覆盖既有直接入口、文件选择、
  凭据通道、恢复输出及 provider 生命周期。
- 收尾定向组：97 passed，包含七类语义更新、未选中对象保留、原生逻辑接口、
  recovery 合同、Filter 安全上下文和两种目录布局的正式 runtime 四操作路径。
- 两种布局以 Reader/Writer 测试替身运行；未启动 Docker/DinD 或连接设备。
  Go 既有 launcher 测试验证 local/DinD 文件映射和新执行身份传递。
- 修改加载后校验接口后，既有 NAT 批次与资源上下文定向回归另有 35 passed。
- pyright 通过；Ansible workflow-stage lint 达 production profile（0 failure）。
  lint 的动态 provider options 加载有提示，不能把 lint 当成模块设备执行证据。
- launcher `build.sh` 运行 Go 测试并产出 linux/amd64、darwin/arm64 二进制及 checksum。
  构建在临时目录执行，未发布。
- strict OpenSpec 校验通过。GitNexus 刷新并执行实际修改符号 impact 及提交前
  detect-changes；核心归一化/依赖路径为 CRITICAL，候选/恢复路径为 HIGH。
  图的动态调用 UNKNOWN 由固定调用点与定向测试补充，未当成无影响证明。
  图流程抽取报告自身预算裁剪；detect-changes 的结果无 partial/truncated，
  软件测试用于实际消费路径，未据“图中没有”推断代码不可达。

## 最终复核修正

2026-09-19 的三路只读复核发现 4 项 P1；此前测试通过不覆盖这些缺陷。
本轮针对发现修正并重新复核：

- Writer 将 HTTPS endpoint 拆成 Collection 的裸主机和显式 api_port，保留
  自定义端口与 IPv6；不支持的 HTTP 写入在调用提供者前拒绝。
- candidate coverage 必须包含所选对象及必要依赖类别，只接受七类受支持资源，
  加载候选和 apply 写前均校验；空范围不能绕过身份占用及漂移检查。
- 静态 Alias 只有明确 enabled=true 时才可用完整 PF 表成员补充活动确认；
  disabled/absent 保留 unsupported，旧表不能将未确认激活提升为成功。
- 阶段漂移检查保留原先相关对象，并发现新引用。A→B 切换不因旧依赖退出当前
  引用集合而误报；旧依赖被外部修改仍停止执行，激活后也使用相同检查。

本轮联合回归 153 passed，pyright 0 errors；workflow-stage 的 Ansible syntax
check 和 lint 通过，lint 为 0 failure / 0 warning。strict OpenSpec、文档链接、
既有候选示例合同检查通过。两路独立只读复核分别覆盖核心与提供者补丁，
旧复现均关闭，修复范围内未发现剩余 P1/P2。真实设备、发布及消费接入边界未改变。

## 能力与接入前提

固定 Collection 与原生返回值边界见 [能力说明](capability-notes.md)。
Filter/NAT/VIP 的同步 configd 成功可确认激活；Groups、Gateway 以及动态 Alias
的 handler ok 不能单独确认成功，会保留 unconfirmed 并停止依赖阶段。静态地址
Alias 只在完整 PF table 成员匹配时补充活动确认；六类资源无独立活动核对时保留
unsupported。配置正确但活动项未覆盖时可为 completed_with_unverified，不能解释为
数据面或业务验收通过。没有虚构 gateway/Group 运行态证明来绕过这个限制。

配置读取复用固定提供者的有界整类列表/详情；显式身份会在输出前过滤，引用分析
只保留相关对象。它不扩大写集合，但设备 API 不支持这些身份的统一精确查询，
仍会读取所需类别；单响应 2 MiB、Reader 会话累计 8 MiB、分页上限 5 页/每页 1000。
超限、不完整、未知必要字段或不兼容原生模式将拒绝执行，不推断不存在。

调用方需使用包含本实现的匹配 launcher/runtime 版本，固定实际镜像 digest，显式
提供单主机静态 inventory、输入与 API 凭据。共享 pending-change 自动观测无可靠
通用接口，调用方必须完成无冲突检查并维持整个窗口串行化，将结论绑定到目标、
候选 SHA-256 和新的 execution_id。output basename 与 execution_id 一致；这不是
分布式锁、跨主机重放服务或调用方策略引擎。不会传递 OP_* 引导凭据，也不依赖 S3。

手册：[OPNsense](../../../../docs/operations/02-opnsense.md)、
[runtime 配置](../../../../docs/runtime-configuration.md)、
[launcher](../../../../docs/runtime-launcher.md)。
[合成示例](../../../../docs/examples/opnsense-workflow/README.md) 包含 request、candidate、
result、recovery 和新的反向 candidate；肯定状态只来自测试替身。

## 后续阶段

发布由仓库既有发布流程承接，消费仓库接入时固定相同接口版本与镜像摘要。
真实设备响应、Groups/Gateway/动态 Alias 的可靠激活证据及现场业务数据面仍需
对应阶段验证；需要这些尚不可证明的成功路径时会阻断，不能依赖合成结果放行。
未建立逐对象证据系统、版本穷举矩阵或额外平台抽象。
