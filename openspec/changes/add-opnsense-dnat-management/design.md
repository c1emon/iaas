## Context

动机见 [proposal.md](proposal.md)。本次范围为两类 NAT（DNAT、1:1 NAT）和 Firewall 接口组，共三类资源；以下 DNAT 细节与新增其他资源章节共同构成设计。现有 `manage-dnat.yml` 只验证列表形状后停止；通用 validator 支持 aliases/vips/gateways/filter-rules 四类。当前固定和项目内实际安装的 Collection 均为 26.1.11，没有 nat_destination。上游 2026-07-15 合入 PR #430，模块仍标为 unstable。SNAT 仅保留在本设计的延期章节，不注册为本轮资源。

上游模块使用 firewall/d_nat 的 get/add_rule/set_rule/del_rule，字段映射对应 OPNsense 26.7 DNat 模型，包括反向 disabled、嵌套 source/destination、natreflection 和 pass。当前只有源码核对，没有新模块的现场读写证据。GitNexus 对 validate_document 的 upstream 分析涉及 13 个对象、9 条流程，评级 CRITICAL，索引落后 HEAD 一次提交；此为共享入口风险提示，实施前须刷新并重做分析。

## Goals / Non-Goals

**Goals:** 将显式声明的 DNAT、1:1 NAT 和接口组接入现有通用管理入口，保留原输入兼容性、增量所有权和配置保存/应用分离。

**Non-Goals:** 全设备 NAT 接管器、端口服务发现、分流策略、跨资源自动事务、全局反射设置与出站 NAT 模式管理、Categories、NPTv6、站点部署。用户接受短暂离线是 infra-ops 迁移约束，不意味着 iaas 可以清空规则或主动制造中断。

## Decisions

### 1. 上游依赖与兼容门槛

采用完整上游 Collection 的不可变 commit，候选从 DNAT 合入提交 `1423500c29f8` 开始；实施第一阶段解析并记录完整 SHA，比较其相对 26.1.11 的差异和新增模块依赖，同时验证本轮 1:1 NAT、DNAT、Groups 的 API 及请求/响应行为。开发环境与 OCI 构建必须用同一固定源，构建时安装，运行时不下载/升级 Collection、不引入 op 或凭据工具。SNAT 的依赖兼容性留待后续 change 单独评估。

不复制模块到 infra-ops，不默认维护 iaas 私有 fork，也不直接使用浮动 latest。若候选引入不兼容公共变更或 DNAT 缺陷，暂停依赖切换并报告所需修正；新增供应商补丁或扩大公共 API 修复须单独明确范围。仅文档标记 unstable 不等于不能接入，但不能用上游作者的实测替代本站实测。

### 2. 独立资源与 NAT 公共约定

| 资源选择键 | 标准文件 / 顶层列表 | 提供者 | 稳定身份 |
| --- | --- | --- | --- |
| dnat | dnat.yml / opnsense_dnat_rules | nat_destination | scope + slug |
| one-to-one-nat | one-to-one-nat.yml / opnsense_one_to_one_nat_rules | nat_one_to_one | scope + slug |
| interface-groups | interface-groups.yml / opnsense_interface_groups | rule_interface_group | name |

本轮两类 NAT 的描述为 `iaas:opnsense:dnat:<scope>:<slug>`、`iaas:opnsense:one-to-one-nat:<scope>:<slug>`。仅公共身份、形状、校验辅助和生命周期约定复用；每类资源独立校验、独立入口、独立提供者。相同 scope/slug 在两类 NAT 间合法；单类内重复拒绝。sequence 不作身份，序号排序域按原生资源分别核对，不能套用 DNAT 的界限到 1:1 NAT。

SNAT 命名预留但延期：后续仍使用 `snat.yml` / `opnsense_snat_rules`、`manage-snat.yml` / `opnsense_snat_source` 以及 `nat_source`。这些名称不在本轮 resource selection、validator、runtime check/generate 或执行入口中注册；SNAT spec 不作为本 change 的 active delta，后续上游修复后由独立 change 恢复。

NAT absent 仅要求身份和 state；present 要求明确的 enabled、sequence、接口和该类必需字段。公共可选布尔源/目的反选及日志缺省 false。不接受自定义 description/uuid/match_fields，禁止按地址或端口猜测旧对象归属。

present 是对本合同支持字段的完整声明：省略可选字段须复位为合同默认值，不能通过 omit 悄悄保留旧值。源/目的端口及翻译端口省略时清除已有约束；DNAT local_port 清除表示沿用报文原目的端口，不是沿用旧配置的翻译端口。反选、log 缺省 false；pool_opts、tag、tagged 缺省清空为原生默认。适配器须按固定提供者采用实际有效的清除值（如显式 null/空值），验证值移除后的幂等，不把 Ansible omit 当作清除。合同未管理的设备字段保持原状；必填字段不能通过省略继承旧值。

首版 DNAT 的原生模式约束为 `nordr=false`（提供者归一化字段为 `no_port_forward=false`），不能把该字段当作提供者不会处理的未知字段。凭据预检后，使用固定 Collection 的只读列举能力按同一稳定身份核对：若 present 匹配的现有 DNAT 对象启用了 `nordr`，在该资源批次首个写入前拒绝，不让提供者默认 false 静默转换免转发规则；已匹配对象的模式无法判定时同样拒绝。不校验或约束未声明对象的模式。absent 仍可按明确身份精确删除，不要求支持其旧翻译语义。此为已知原生形态检查，不新增免转发能力或私有 API 客户端；固定依赖的读取结果必须能提供该判断，否则先报告兼容阻塞。1:1 NAT 不借用 DNAT 的 `nordr` 字段。

候选 Collection 的 `oxlorg.opnsense.list` 已有 `target: nat_destination`，按其返回 data 中的 description 精确匹配，只检查选定 DNAT 身份；读取归一化字段 `no_port_forward`，不假定返回原生键 `nordr`，也不输出完整设备列表。

#### 2.1 DNAT 合同

标准文件为 `dnat.yml`，唯一顶层键 `opnsense_dnat_rules`，值为列表。单条输入采用 `scope` + `slug` 生成稳定描述 `iaas:opnsense:dnat:<scope>:<slug>`，以 description 匹配；用户不得独立填写 description、uuid 或 match_fields。缺失/重复身份、未知字段在写前失败；名称或顺序改变不能被悄悄解释为旧规则清理。

| 字段 | 首版约束 |
| --- | --- |
| scope / slug | 必填，沿用过滤规则身份字符约束，DNAT 使用独立描述前缀 |
| state | 必填 present / absent；absent 仅需身份和 state，不依赖待删对象的旧端口或目标 |
| enabled / sequence / interface | present 必填 bool、1–999999 的整数、非空接口列表 |
| ip_protocol / protocol | present 必填，inet/inet6/inet46 和固定提供者支持的协议；端口字段仅用于提供者允许的传输协议 |
| source_net / destination_net | present 必填，单个 IP/CIDR/别名或提供者支持的特殊标记，如 any、wanip；首版不接受隐式多目标字符串拼接 |
| source_port / destination_port | 可选字符串，字面端口、合法端口别名或原生支持的范围；省略清除已有端口限制，不使用任意字符串兜底 |
| local_port | 可选字符串，单个数值端口、原生已知端口名称或合法端口别名；不接受字面范围（如 8000-8010）。省略清除旧翻译端口，沿用报文原目的端口 |
| source_invert / destination_invert / log | 可选严格 bool，缺省 false；反选仅一个匹配目标 |
| target | present 必填，原生支持的 IP 或别名；已知静态地址族不匹配拒绝，外部别名留给在线解析 |
| nat_reflection | present 显式填写空字符串、purenat 或 disable；空字符串表示继承设备现值，不设置全局开关 |
| associated_rule | present 显式填写空字符串、pass 或 rule；分别表示手工过滤、NAT 直接放行、设备关联过滤规则 |
| pool_opts / tag / tagged | 可选，使用固定提供者的合法枚举和字段约束，不派生站点策略 |

首版不提供 no_port_forward/nordr 例外资源：当前上游即便 nordr 仍强制要求 target，与原生免转发语义不一致；拒绝该字段并明确能力边界，不编造目标绕过校验。这不阻断正常端口转发。

端口合同取固定提供者与原生模型的交集：[DNat.xml](https://raw.githubusercontent.com/opnsense/core/stable/26.7/src/opnsense/mvc/app/models/OPNsense/Firewall/DNat.xml) 的 local-port 未启用 EnableRanges，[PortMappedField](https://raw.githubusercontent.com/opnsense/core/stable/26.7/src/opnsense/mvc/app/models/OPNsense/Firewall/FieldTypes/PortMappedField.php) 继承的 [PortField](https://raw.githubusercontent.com/opnsense/core/stable/26.7/src/opnsense/mvc/app/models/OPNsense/Base/FieldTypes/PortField.php) 默认关闭范围；不能仅按 Collection 文档概述接受范围。

不将 destination_net=any 或 associated_rule=pass 一概认定错误：它们对某些通用 DNAT 用途合法。是否只匹配 WAN、是否与分流冲突、原有 UDP 是否需要，属于 infra-ops 的服务意图与环境审查。

#### 2.2 SNAT 延期设计与命名预留

SNAT 后续仍预留 `snat.yml`、`opnsense_snat_rules`、`manage-snat.yml`、`opnsense_snat_source` 和 `nat_source` 命名。本轮不注册 `snat` 资源、不勾选 SNAT 任务、不加载或执行 SNAT，以下内容只作为上游修复后的后续设计，不计入本轮三资源/两类 NAT 验收。

后续 present 计划要求单个 `interface`、`ip_protocol`、`protocol`、`source_net`、`destination_net`、`target`；可选 `source_port` / `destination_port`、`target_port`、`static_port`、反选与日志。`target_port` 采用提供者实际的整数端口 1–65535，不能沿用 DNAT 的字符串/别名合同；启用 static_port 时拒绝同时指定 target_port。源/目的端口只支持固定提供者和 API 实际共同支持的字面端口/范围，不承诺文档未支持的端口别名。

`target` 支持已验证的 IP/网段、别名或原生接口地址标记，不能把一个字段的地址语法套到所有 NAT 字段。首版不暴露 no_nat：当前提供者在 no_nat 时仍要求 target，须先解决其语义才能扩展，不能填虚假目标。管理手工声明的 SNAT 不等于管理整套出站 NAT 模式或自动规则；同现有自动 SNAT 共存的顺序及模式前提由调用方核对，iaas 不为使规则生效自动切换 manual/hybrid。

#### 2.3 One-to-one NAT 合同

present 要求单个 `interface`、`type`（binat/nat）、`external`、`source_net`、`destination_net`，以及显式逐规则 `nat_reflection`（enable/disable）。不提供 DNAT 式端口、关联过滤模式或多接口列表；不将 DNAT 的 purenat 或空字符串照搬到此模块。反选、log、enabled 使用严格 bool。

对字面地址检查同族和映射范围；BINAT 的显式内外网段必须等大，nat 类型不强行套用等大规则。由提供者支持的合法外部别名留给在线解析；动态内容不能被说成已证明范围相等。首版承接固定模块对应的 IPv4 1:1 功能，IPv6 前缀转换不借此宣称为 NPTv6。

#### 2.4 Groups 合同

这里是 Firewall 接口组，不是账户组。身份为实际组 `name`，沿用提供者/原生名字规则（最长 15 字符、字母数字下划线且不能以数字结尾）；不加 NAT 的 scope/slug、enabled 或自定义 UUID。present 要求非空且不重复的 `members`、显式 bool `gui_group`、整数 sequence 0–9999；description 为可选说明，不作为身份。absent 只需 name/state。

组名保持原生大小写，不自动转小写。现有 filter-rules.interface 与 context.interface_networks 的物理接口正则只接受小写，须作最小兼容：在原生支持组引用的位置接受合法组名（包括 `Internal`），对上下文中的同名键保留大小写；VIP/Gateway 等物理接口字段的约束不因此放宽。选定组声明参与已知引用检查，未选定合法组引用保持外部未解析状态。组成员不自动变成 context 中的网段事实，也不作为放宽既有 deny/反选保护的证据；所需静态网段由调用方显式提供并沿用原有覆盖校验。

Groups present 同样完整管理其支持字段：省略 description 清除旧说明，不能保留上次值；未声明的组及未管理的原生字段保持原状。

成员填写固定 API 实际接受的接口标识。26.1.11 文档称 network-port 名，26.7 原生模型通过 InterfaceField 解析；实施前必须用对应 API 选项核对，明确记入通用手册，不能猜测 optN 和设备名可互换或自动按界面描述转换。首版不支持嵌套组；未声明的现有系统/VPN 组，包括空成员组，保持原状。

变更成员会改变组规则适用范围；gui_group 仅按原生 nogroup 反向字段处理，不当作防火墙总开关。组名是不可变身份；改名是调用方显式新建、迁移引用、退役旧组，不能利用底层重命名隐式重写全设备规则。

选定输入中存在对待删除组的存活引用则在写前失败；设备上的未选定引用由原生 whereUsed 删除保护兜底，错误明确报告，不自动删依赖规则、不扩权或绕过保护。组规则允许哪些来源/目的、位置如何保留 ACL 属于调用方；iaas 不把接口组成员当作来源地址授权集合。

### 3. 分派与校验隔离

新增三类都是可选资源。已有四文件目录和已有场景不新增必填项；未选择某一新增资源时不自动发现其文件并纳入 mutation。单资源验证支持本轮三个 resource key（`dnat`、`one-to-one-nat`、`interface-groups`）；`snat` 保留为延期命名但当前选择必须拒绝。runtime 场景显式引用对应标准文件，新增接入仅为离线 check/generate，不新增 launcher 的 OPNsense apply 操作，现有 diagnose 保持原职责。目录式旧默认仍验证旧四类，新增三类由显式资源/场景选择验证，文档清楚列出覆盖集合。

写入沿用受支持 iaas checkout 中的直接 Ansible 入口，调用方通过 inventory 的 opnsense 主机组及显式 --limit 选择设备：

| 资源 | automation/ansible/playbooks/opnsense/ 下的入口 | 源文件覆盖变量 |
| --- | --- | --- |
| dnat | manage-dnat.yml | opnsense_dnat_source |
| one-to-one-nat | manage-one-to-one-nat.yml | opnsense_one_to_one_nat_source |
| interface-groups | manage-interface-groups.yml | opnsense_interface_group_source |

源路径默认 `${ENVIRONMENT_DIR}/ansible/vars/opnsense/<标准文件>`，调用方可显式覆盖为 generate 输出的对应文件路径；生成成功不自动执行。每个本轮 playbook 先验证该源文件，再加载对应顶层列表，并对实际加载列表使用同一 validator 复验，然后才做凭据预检和 API 操作。--check 只读；直接 Ansible 正常运行是本 change 所称执行/apply，不意味着 launcher 已支持写操作，也不新增其 operation/effects/scope。多文件场景离线校验同时检查已选择资源的已知引用；单资源 playbook 仅对实际输入作同合同校验，不声称检查未传入的其他文件，设备外部引用仍由原生保护负责。SNAT 的 `manage-snat.yml` 和 `opnsense_snat_source` 仅为后续 change 预留，本轮不得被选择。

先本地整批校验，再载入并复验实际 Ansible 输入，最后凭据预检和 API。复验防止 extra-vars/加载优先级改变已验证对象；失败只报告字段和安全身份。缺失模块或版本不符在设备写入前失败。引用检查只覆盖可静态证明的类型/地址族/选定别名，不能把整个设备闭合依赖图作为准入条件。

新增三类 validator 与分派独立；既有四类只作上述组引用位置的兼容接入，不顺带重构其他合同或弱化原有保护。SNAT 不进入本轮 validator 或分派。新增或删除通用字段必须和模块实际接收参数一致，不能由 Ansible 静默忽略未知输入。

### 4. 保存、应用与恢复

只增量处理清单中稳定身份：present 创建/更新/启停，absent 精确删除；省略对象保持不变。一个描述匹配多个现场对象则失败，不任选一个。既有非 iaas 描述对象由调用方显式制定迁移，iaas 不按相似地址/端口认领，不按前缀清空设备。

两类 NAT 各 CRUD 强制 reload=false；单资源整批成功且有变化时执行一次受支持的对应 NAT apply，check mode 绝不激活。配置保存失败报告可能部分保存，并停止激活；apply 失败报告保存态与运行态可能不同。沿用显式布尔 `opnsense_force_reload` 恢复无变更重试，不承诺自动回滚。SNAT 不进入本轮激活或验收。

associated_rule=rule 产生的设备关联对象归该 DNAT 管理关系，调用方不得再以独立 filter-rules 声明同一生成对象；manual 模式的独立过滤规则由调用方显式组合。模式切换/删除对关联对象的行为须按固定模块与原生 API 验证，不能只测 DNAT 返回 changed。

Groups 使用固定 Collection 的 `oxlorg.opnsense.raw` 以固定路径 `firewall/group/reconfigure` 执行一次 POST，而非假定 NAT apply；不向调用方暴露任意 endpoint/body，不维护私有 API 客户端。遵循同样的 check-mode/失败/显式恢复约定：check mode 跳过 POST，成功变更后才 reconfigure，显式 force-reload 只允许固定路径恢复。该 reconfigure 会注册接口并重载过滤规则，不能宣称只刷新该组。所有资源的激活都可能重载设备共享规则集，因此调用方须确认没有未经审查的其他待应用配置。

多资源文件可在同一离线场景校验/生成，执行仍按显式单资源目标逐批操作，不新增跨资源事务或自动顺序优化。存在依赖时，由 infra-ops 安排先组/别名、后引用规则；删除反向进行，并确保每一实际批次的存活引用合法。任一阶段失败不得自动推进下一阶段。不会因 NAT 和过滤规则共享关联对象而重复管理。

### 5. 两仓与验证边界

| 所有者 | 负责 | 不负责 |
| --- | --- | --- |
| iaas | 两类 NAT 和 Groups 原生参数、通用输入/引用校验、精确增量执行、版本固定、通用操作说明 | 站点端口、服务意图、共享开关决策、全量接管、分流分类 |
| infra-ops | 现场盘点、规范化声明、DNAT/1:1 NAT/过滤组合、显式迁移退役、共享设置与恢复、离线窗口 | 复制 Collection、私有 API 客户端、通用原生字段实现 |
| OPNsense/Collection | 原生资源、关联规则和 apply 的设备行为 | 本仓库对站点配置正确性的承诺 |

软件验收使用本轮三类资源中的代表性校验正反例、模块参数/返回转换、幂等、check mode、删除、失败及恢复路径；固定完整 Collection 的 DNAT、1:1 NAT、Groups 加载和旧资源回归必须通过。DNAT 对 `nordr` 的匹配对象必须在首个写入前完成只读检查；Groups reconfigure 只允许固定 Collection raw 的固定路径。允许受保护的只读响应作为兼容样本，但不保存秘密/会话原文。SNAT 不计入本轮验收，待上游修复后单独恢复。本站真机写入/回流/短暂离线验证由 infra-ops 在后续窗口执行；iaas 软件完成不宣称现场通过。

## Risks / Trade-offs

- [未正式发布的依赖] → 固定完整 SHA，记录相对正式版差异及测试范围；后续正式版本替换是显式升级。
- [公共分派/校验回归] → 保留四文件兼容，增加有/无三类资源场景验证，实施前刷新图分析。
- [NAT 关联过滤与共享反射有外部效果] → 参数显式，测试关联生命周期；现场影响与恢复由调用方审查，不自动改变全局设置。
- [上游 nordr 限制] → DNAT 首版明确不支持免转发例外，并在首个写入前做 `nordr` 只读检查；SNAT 的 `no_nat` 仍属于延期设计，不承诺本轮原生 SNAT 能力。

## Migration Plan

先完成本轮三资源依赖兼容评估和公共准入，再逐阶段接入 DNAT、1:1 NAT、Groups，最后完成三资源组合回归及文档。SNAT 保留命名和延期设计，待上游修复后由独立 change 恢复 `snat.yml` / `opnsense_snat_rules` / `manage-snat.yml` / `opnsense_snat_source`。每阶段独立提交，不在一个实现批次中混做两仓。发布镜像和让 infra-ops 消费新版本是后续显式交付动作；没有新版本前调用方仍使用现有无 DNAT 写能力的运行时。

本 change 不触发现场旧规则删除。调用方先形成对象对照、激活批次和反向声明，再进行授权迁移。运行时回退只能恢复旧工具版本，不能自动恢复已保存的 NAT/Groups；设备恢复须由调用方提供原声明和操作步骤。
