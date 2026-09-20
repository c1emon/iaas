# 2. OPNsense

本章覆盖 OPNsense 的 API 接入、只读导出、别名、过滤规则、策略路由网关、
IP Alias VIP，以及显式选择的 DNAT、1:1 NAT 和 Firewall 接口组。它在 PVE 与
VM 创建前定义网络边界，但仓库不自动管理 DNS、DHCP、物理接口、普通路由、
系统升级或站点策略组合。

## 2.1 准入与责任边界

开始前必须已有：交换机 L2 路径、OPNsense 本地/物理控制台、API 凭据、已审查
的接口标识符、目标网段/端口、回退方案和变更记录。API 配置只管理其声明的
对象；它不会推断“某个 K3s 服务需要开放什么端口”。

`$ENVIRONMENT_DIR/inventory/foundation.yml` 可将 OPNsense 声明为 K3s 前置的
基础服务；该文件只是恢复元数据。健康探针通过 `make foundation-health` 是
在线只读证据，不替代本章的 API 或防火墙规则审查。

当前可管理范围是 API 连通、只读查询/导出/快照、调用方声明的别名、IP Alias VIP、PBR
gateway、API-backed new filter rules，以及 DNAT、1:1 NAT、Groups。
SNAT 保留命名占位但尚未实现。DHCPv4/v6、RA/PD、WAN/PPPoE、VLAN interfaces、
CARP、Proxy ARP、Other VIP、静态路由、gateway groups、legacy firewall/management
rules、默认防火墙策略和关键公网入口不在本仓库管理范围。不要把“能导出”误解为
“可回写/可管理”；软件测试通过也不等于目标设备或数据面已验收。

## 2.2 配置文件与连接参数

| 文件 | 作用 | 约束 |
| --- | --- | --- |
| `$ENVIRONMENT_DIR/ansible/inventory.yml` | `opnsense` 组、主机别名、API host/FQDN。 | 环境源文件。 |
| `$ENVIRONMENT_DIR/ansible/group_vars/opnsense.yml` | `opnsense_api_url`、`opnsense_ssl_verify`、API key/secret 入口。 | Key/secret 仅用环境变量。 |
| `$ENVIRONMENT_DIR/ansible/vars/opnsense/*.yml` | 声明式期望状态，覆盖本章七类标准资源。 | 不从 export 复制回写。 |
| `$OUTPUT_DIR/runtime/exports/opnsense/<inventory_hostname>/` | 按设备隔离的 API 导出。 | 本地观察产物，不是 apply 输入。 |

| 变量 | 含义 | 约束 |
| --- | --- | --- |
| `opnsense_api_host` | API 主机或地址。 | 必须与实际管理端点匹配。 |
| `opnsense_api_url` | 由 host 派生的 HTTPS URL。 | 用于操作者理解；模块默认使用 host。 |
| `opnsense_ssl_verify` | API TLS 校验开关。 | 由调用方声明；正常使用应启用 TLS 校验并提供可信 CA。 |
| `OPNSENSE_API_KEY` / `OPNSENSE_API_SECRET` | API 身份。 | 调用方通过 `.env.opnsense.tpl` + `op run` 或传统 Secret 注入相同变量。 |

## 2.3 声明式资源参数

### 别名：`vars/opnsense/aliases.yml`

根键为 `opnsense_aliases`，每项使用 `alias_multi` 的兼容字段。

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `name` | 别名稳定名称。 | 遵循固定版本语法，最多 31 字符；字母或单下划线前缀，只含字母数字下划线，不允许双下划线前缀。 |
| `type` | `host`、`network`、`port`、`urltable`、`networkgroup`。 | 与 `content` 类型一致；已有名称不能直接改变类型。 |
| `content` | 地址、网段、端口、HTTP(S) URL 或别名名称列表。 | 按类型校验；组成员必须是地址兼容别名。 |
| `updatefreq_days` | URL table 的刷新周期（天）。 | present 必填，absent 可省略；其他类型禁止。使用引号字符串，如 `"1"`、`"0.5"`，最小 0.1 且最多一位小数，不允许丢失精度。 |
| `description` | 人类可读用途。 | 不作为秘密或业务配置载体。 |
| `enabled` | 是否启用。 | 显式布尔值。 |
| `state` | `present` 或 `absent`。 | `absent` 是变更操作，先审查引用。 |

URL 由调用方选择，不允许用户名密码、fragment 或嵌入凭据；普通查询参数也必须是非秘密配置。
还须符合固定 Collection 的 URL 语法；IPv6 字面地址、单标签主机名等不受该版本支持的形式会在离线阶段拒绝。
运行时不下载或改写列表；动态 Alias 遵循 OPNsense 原生内容与缓存刷新语义，不由执行机自行解析或增加强制刷新。

组引用会先在本地校验，再只读解析外部定义。按依赖顺序创建成员和组，先释放旧引用、后按设备现有依赖反序删除。
未声明的对象不被接管。删除仍受设备的最终引用保护；失败可能留下已保存的部分配置，不会自动回滚或激活。
Check mode 使用读取到的配置生成计划，不写入临时成员，也不触发 reload。
旧配置中含连字符、点、数字开头或 32 字符的别名名称将被提前拒绝；按设备命名规则由调用方规划迁移，工具不自动改名。

通用 schema/组合示例见 `tests/fixtures/opnsense-capabilities/`，仅供审查，不能直接作为部署策略。

### 过滤规则：`vars/opnsense/filter-rules.yml`

根键为 `opnsense_filter_rules`。`scope` 与 `slug` 是不可变身份；系统生成
`iaas:opnsense:filter:<scope>:<slug>` 描述并以其匹配，禁止手写 `description`。

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `scope`、`slug` | 稳定规则身份。 | 小写数字连字符格式；修改相当于新规则。 |
| `state`、`enabled` | 生命周期和启用状态。 | `state` 只能为 `present`/`absent`。 |
| `sequence` | 规则顺序。 | 整数 1–99999；推荐 1–99 核心、100–199 策略路由、200–499 特例、900+ 宽泛默认规则。 |
| `interface` | OPNsense 接口 ID 列表。 | 用 API 接受的 ID，不使用 UI 显示名。 |
| `direction`、`action`、`quick` | 匹配方向、动作、快速匹配。 | 先用 readonly/export 确认现有顺序与语义。 |
| `ip_protocol`、`protocol` | IP 族与传输协议。 | `inet`/`inet46` 等须与地址和目标服务一致。 |
| `source_net`、`destination_net` | 单值或 YAML 列表。 | 列表会归一化为逗号分隔；拒绝/阻断规则不得把自身接口列为目的地。 |
| `source_port`、`destination_port` | 可选单值、列表、范围或 alias。 | 未定义表示不限；保留字符串以避免范围被 YAML 误解。 |
| `source_invert`、`destination_invert`、`gateway`、`log` | 可选反向匹配、PBR 网关和日志。 | 仅在明确需求时加入；空 `gateway` 表示不指定。 |

### 策略路由网关：`vars/opnsense/gateways.yml`

根键为 `opnsense_gateways`。每项必须声明 `name`、`interface`、`ip_protocol`、
`gateway`、`default_gw`、`far_gw`、`monitor_disable`、`monitor_noroute`、`monitor`、
`force_down`、`latency_low`、`latency_high`、`loss_low`、`loss_high`、`interval`、
`time_period`、`loss_interval`、`data_length`、`priority`、`weight`、`description` 和
`state`。

其中 `interface` 是 API 接受的接口/port 标识，不是 UI 标签；`default_gw` 必须为
`false`，因为此工作流不得接管默认路由；`monitor*`、延迟/丢包阈值和 interval
共同定义探测敏感度，不能把适用于实验链路的值直接套用于生产出口。

仓库使用下文固定 SHA 的 `oxlorg.opnsense`（候选版本号仍为 `26.1.11`）。它将 API 有时缺失的 `fargw`
处理为可选的 `far_gw`；不得 patch 控制机上已安装的 collection。升级 collection
前，先在隔离环境重新运行语法/离线校验，再确认这个兼容性仍存在。

### VIP：`vars/opnsense/vips.yml`

根键为 `opnsense_vips`。每项必须有 `description`、`interface`、`address`、
`bind`、`expand` 和 `state`。`address` 必须是 CIDR；当前工作流固定 IP Alias
模式。`bind`/`expand` 的含义以 OPNsense API 为准，变更前必须确认该接口和
现有服务不会因 ARP/地址宣告变化失联。

### 三类新增资源：DNAT、1:1 NAT 与接口组

三类资源均为可选输入；原有 aliases、vips、gateways、filter-rules 四文件的默认
目录校验保持不变。未选中的资源不会被自动发现、读取或写入，空列表也不表示
清空设备对象。标准声明示例见 [`docs/examples/opnsense-nat/`](../examples/opnsense-nat/)，
其中使用文档保留地址，不能直接视为现场策略。

| 资源 | 标准文件 / 根键 | 直接 Ansible playbook / 源变量 |
| --- | --- | --- |
| DNAT | `dnat.yml` / `opnsense_dnat_rules` | `playbooks/opnsense/manage-dnat.yml` / `opnsense_dnat_source` |
| 1:1 NAT | `one-to-one-nat.yml` / `opnsense_one_to_one_nat_rules` | `playbooks/opnsense/manage-one-to-one-nat.yml` / `opnsense_one_to_one_nat_source` |
| Firewall Groups | `interface-groups.yml` / `opnsense_interface_groups` | `playbooks/opnsense/manage-interface-groups.yml` / `opnsense_interface_group_source` |

源变量默认读取 `$ENVIRONMENT_DIR/ansible/vars/opnsense/<标准文件>`，也可显式指向
runtime `generate` 产物。每个直接 playbook 都必须先校验选定文件，再校验 Ansible
实际加载的列表，最后才做凭据预检和 API 操作；`--check` 不执行 CRUD 或激活。
对这三类新增资源，runtime 只提供 OPNsense 的 `check`/`generate`，不增加 launcher
apply；生成文件不会自动调用设备 playbook。既有 `diagnose` 入口保留原有有界只读
职责，见 2.6，不受新增资源 runtime 范围限制。

SNAT 暂不属于可选资源，`snat.yml`、`opnsense_snat_rules`、`manage-snat.yml` 和
`opnsense_snat_source` 仅保留给后续上游修复后的 change。当前选择 SNAT 必须失败，
不访问凭据或设备，也不计入本轮验收。

#### DNAT

DNAT 使用 `scope` + `slug` 生成 `iaas:opnsense:dnat:<scope>:<slug>` 稳定身份；
`present` 必须完整声明受支持字段，`absent` 只需身份和状态；`sequence` 为整数
1–999999。`nat_reflection` 枚举为 `""`（继承设备现值）、`purenat`、`disable`，
`associated_rule` 枚举为 `""`（手工过滤）、`pass`（NAT 直接放行）、`rule`
（设备临时关联过滤规则），两者在 `present` 中都必须显式填写。省略可选字段会
清除旧值并恢复合同默认：源/目的/翻译端口清除旧限制，`pool_opts`、`tag`、
`tagged` 清空；反选和日志默认 `false`。`local_port` 接受
单个端口、原生端口名或合法端口别名，不接受字面范围；省略它会清除旧翻译端口，
恢复报文原目的端口。`nordr` 免转发例外不属于首版合同；凭据预检后、批次首个
写入前，固定 Collection 只读检查匹配对象的 `nordr`（归一化字段
`no_port_forward`），为真或无法判定时拒绝整批。

`associated_rule=rule` 由 OPNsense 在 filter reload 时临时生成关联规则，没有独立
UUID 或持久 filter 配置。切换关联模式、禁用或删除 DNAT 后，下一次原生 filter
reload 会按新状态移除或重新生成它；不要将该规则再声明为独立 filter 对象。

#### 1:1 NAT

1:1 NAT 使用 `scope` + `slug` 生成 `iaas:opnsense:one-to-one-nat:<scope>:<slug>`；
支持原生 `nat`/`binat`、单接口、IPv4 地址/网段和逐规则反射；`sequence` 为整数
1–99999。`binat` 的字面内外
网段必须等大，`nat` 不套用该限制；端口、NPTv6 和 DNAT 关联字段均被拒绝。它
只管理声明对象，不推导 VIP、过滤规则或全局反射设置。

#### Firewall Groups

Groups 是 Firewall 接口组，不是账户组。身份为原生大小写敏感的 `name`；present
要求成员、`gui_group` 和 sequence，absent 只需 name/state。不支持嵌套组；未声明的
系统/VPN 组保持不变。filter-rules 的 `interface` 和
`opnsense_filter_rule_context.interface_networks` 可引用合法的 mixed-case 组名，
并保持原有 deny/inversion 保护；VIP/Gateway 的物理接口字段仍拒绝大写组名。
`members` 必须填写设备原生配置接口 key（例如 `lan`、`opt1`）；设备端口名、
界面显示名称和 GUI 标签不与这些 key 自动互换。组名首尾不能是数字，`sequence`
为整数 0–9999。

删除前会检查选定 filter/DNAT/1:1 NAT 声明中的存活引用；设备外部引用交由原生
whereUsed 保护，合法外部组引用不要求离线闭合。成员不是地址授权事实，也不会自动
生成 ACL。

整体引用检查在离线 `check`/`generate` 中显式选定 Groups 与相关 filter-rules、DNAT
或 1:1 NAT 时执行：选定的存活规则不能引用被选为 `absent` 的组，组成员不能是
另一接口组。单资源 direct playbook 只验证传入的本资源列表；未随本次选择的
其他资源引用交由设备原生 whereUsed/删除保护处理，不能据此推断离线闭合。

每批 Groups 变更逐项禁止 reload，成功后只用固定 Collection 的
`oxlorg.opnsense.raw` 调用固定 `POST firewall/group/reconfigure` 一次；不暴露任意
endpoint/body，也不引入私有 API 客户端。该 reconfigure 会注册接口并重载共享过滤
规则，不能当作只刷新组本身。

固定 Collection 源为 Git SHA
`1423500c29f88da9ba8147a23fc64006cf464159`；候选版本仍标为 `26.1.11`，DNAT
模块标记为 unstable。SHA 固定只说明依赖可复现，不能替代目标设备 API、写入和
连通性证据。

## 2.4 操作流程

先在仓库根目录运行离线 schema 验证：

```bash
make opnsense-validate
```

三类新增资源必须显式选择。例如：

```bash
PYTHONPATH=automation/src uv run python -m iaas_automation.opnsense_validation \
  --resource dnat --file "$ENVIRONMENT_DIR/ansible/vars/opnsense/dnat.yml"
```

`one-to-one-nat` 和 `interface-groups` 使用相同命令分别替换 resource 与文件路径。
不传入的资源不会被校验或执行；`snat` 当前不是合法 resource。

以下为调用方 `op run` 注入示例；传统 Secret 已注入同名变量时直接执行 `uv run`。
调用方 group vars 负责将环境变量映射为 Ansible API 连接变量。
然后在 `automation/ansible/` 目录运行在线只读 API smoke、导出
或快照。导出写入本地 `$OUTPUT_DIR/runtime/exports/opnsense/<inventory_hostname>/`，不改设备配置；快照/导出内容可能含
敏感信息，应按本手册的本地观察产物规则处理。

```bash
export OPNSENSE_HOST="your-firewall-inventory-host"
cd automation/ansible

op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/readonly.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/export.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/snapshot.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"
```

导出可包含 firewall aliases、Unbound host overrides/forwarding、DHCPv4/v6
leases 和 IPv6 prefix lease 等观察数据。前 3 类可帮助后续人工审查；所有 export
都不是期望状态输入，DHCP lease 更不是 DHCP 配置。每次写入前先运行 snapshot，
并尽可能在 OPNsense UI 中创建合适的 savepoint。

别名、规则、网关和 VIP playbook 是变更操作，依次先本地验证 YAML、再 API
credential preflight、再仅处理声明项、最后 reload 对应目标。各资源的唯一执行
入口如下：

```bash
# aliases.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-aliases.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# filter-rules.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-filter-rules.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# gateways.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-gateways.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# vips.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-vips.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# dnat.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-dnat.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# one-to-one-nat.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-one-to-one-nat.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"

# interface-groups.yml
op run --env-file "$OPNSENSE_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/opnsense/manage-interface-groups.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$OPNSENSE_HOST"
```

一次只变更一种资源类别，并在每次变更后使用 readonly/export 复核。尤其不得
把 Gateway API 用于默认路由接管，也不得将未知的 export 原样作为期望状态。
同一规则集不得无迁移计划地混用手工与 Ansible 所有权；alias 类型变更也不得
由自动 delete/recreate 猜测完成，必须以明确变更单处理。

每个 managed playbook 默认仅在配置发生变化后激活固定资源 target，普通 no-op
不 reload；`--check` 始终不激活。模块内自动 reload 已显式关闭。DNAT 和 1:1 NAT
在整批 CRUD 成功后各自激活一次；Groups 使用上节限定的 raw reconfigure。若 CRUD 批次失败，
之前的项目可能已保存，但本次不会继续 reload，也不自动回滚。若最后 reload 失败，
输出明确区分保存与激活；检查设备后，可用同一 playbook、输入和目标重试，并附加
`-e '{"opnsense_force_reload": true}'`。此选项允许配置已无差异时再次激活。
必须使用 JSON/YAML boolean；`-e opnsense_force_reload=true` 的字符串形式会被拒绝。

Gateway 数值边界与当前固定 Collection 一致：priority 为 0–255，weight 为 1–5，
latency/interval/time_period 为 1–9999，loss_low/high 为 1–99，data_length 为 0–9999。
loss_interval 仅声明整数；工作流不增加 Collection 未声明的范围。整个期望批次在
凭据访问和写入前校验。deny rule 的管理接口保护会同时考虑 destination_net 与
destination_invert；排除自身接口的反选与包含自身接口不是同一种规则。

直接 Ansible 入口保持原有批次语义；launcher 使用下节的候选、漂移检查和分阶段
save/activate 工作流。两种入口都需要调用方授权、编排和限 host，分别记录
软件校验、设备写入与数据面验证结果。

## 2.5 Runtime 配置工作流

Runtime 的 OPNsense 入口是 `read`、`plan`、`apply` 和 `verify`。它们使用
环境文件中的显式 alias：`inventory` 始终需要；`read`/`plan` 需要 `request`；
`apply`/`verify` 需要 `candidate`；恢复计划可使用 `recovery`，但不能同时声明
期望资源输入。`plan` 会先校验并加载所有显式声明的七类标准资源文件，再由
`request.selection` 选择本次候选的执行集合；未选中的已声明文件仍属于候选上下文。
未知 input 名称、未声明的选择身份和不完整的请求会在准备凭据前拒绝。

本次确认合同只升级候选和结果材料：`candidate`、`result`、`recovery` 使用
workflow schema v2；`request` 继续使用 v1，launcher 的 `interface_version` 也继续
使用 v1。旧 v1 候选在 apply/verify 中被拒绝，须重新 plan。v1 恢复材料仍可受限读取，
仅用于显式选择且后态已核清的配置逆向计划，不继承旧激活结论。request 和 launcher
不因材料版本升级而自动迁移。

本工作流以 OPNsense 26.7.3 源码作为能力说明基线。默认不探测精确固件版本；可选 inspect
中的相应检查仍有版本限制，版本缺失、不可读或不匹配时在该诊断中报告未知或不支持，
不影响默认准入。默认完成基础是配置保存、配置回读和原生激活成功；Alias、Gateway 和
Firewall Group 的深度证据缺口固定输出不可关闭 stderr 警告并写入 result，继续默认流程。
普通 no-change 不创建动作要求。能力结论以
[只读能力核对](../../openspec/changes/archive/2026-09-20-extend-opnsense-activation-confirmation/capability-notes.md)
为准；其中固定 Collection 的源码事实不能跨版本推断为现场支持资格。

既有基线工作流已在本实现分支完成软件验证；本次确认扩展仍受上述版本和能力闸门
约束。使用前必须选择包含这四个操作的匹配 launcher/runtime 版本和实际镜像
digest，不能据此推断既有已发布镜像已经支持。
工作流 inventory 必须自包含：将 `opnsense_api_host` 和 `opnsense_ssl_verify` 写在
所选主机或其组的内联 vars 中，不会自动加载相邻 `group_vars`。API 凭据由调用方
注入环境变量，不写入 inventory 或候选。apply 使用固定 Collection 的 HTTPS
通道；endpoint 可带显式端口（包括 IPv6 地址），会映射为裸主机与 api_port。
HTTP endpoint 可用于只读适配，但不能用于 apply，也不会被静默改为 HTTPS。

| 操作 | 输入 | 副作用 | 相对新 output 目录的主要结果 |
| --- | --- | --- | --- |
| `read` | inventory、request | 在线只读 | `diagnostics/result.json` |
| `plan` | inventory、request、显式 desired inputs | 在线只读 | `plan/candidate.json`、`plan/candidate.sha256`、`plan/result.json` |
| `apply` | inventory、candidate、绑定的 options | 可能保存配置并激活 | `recovery/result.json`、`recovery/recovery.json` |
| `verify` | inventory、candidate | 在线只读 | `diagnostics/result.json` |

`read` 不需要 desired inputs；其 `selection: {aliases: all}` 表示读取全部可观察
Alias。在 plan 中，同样的选择表示声明文件中的全部 Alias，不意味着接管设备上的
其他对象。明确身份选择的形式为 `aliases: [[NAME]]`；空列表不选对象。
已有对象必须在 request 的 `managed` 或 `adopt` 中显式列出本次选择的身份，
未选中对象保持不变。删除用标准声明的 `state: absent`，不以“从文件移除”代替。

普通 no-change 不保存、不 reload。要恢复激活，须在新 request 的
`activation_recovery` 中列出所选身份并重新 plan；它仍受漂移和共享激活准入约束。
apply 的 `check_mode: true` 只执行准入及材料准备，不保存或激活，但仍需在线读取
和有效的调用方检查结论。以上操作不使用 OpenTofu/S3 state。

确认范围按当前能力边界处理：

默认流程只确认保存、配置回读和原生激活；PF、接口组和 runtime 深度事实由独立
inspect 可选提取。以下规则用于说明默认结果、固定警告与深度报告边界，不能作为设备验收声明。

| 资源或事实 | 当前规则 |
| --- | --- |
| Alias 当前活动成员 | 默认不调用深度成员核对；需要时由 inspect 比较完整 PF 表、IPv4/IPv6 地址语义和必要依赖。成员匹配不提升本次 activation。 |
| port Alias | inspect 从固定 API 消费者配置和 PF 规则原文按原生 UUID 关联，比较协议、源/目标端口及范围；不创建验证规则，也不证明本次 reload 完成。 |
| Gateway / Firewall Group | 默认只确认保存、回读和原生激活；inspect 按用途核对路由、监控配置、内核组成员及已加载规则。不要求默认路由或 ping，不创建消费者。深度缺口以固定警告和 result 保留。 |
| `verify` | 默认返回 `fully_verified`，scope 为 `saved_configuration`，`active` 为 `not_attempted`；不追认历史激活、不声称运行态或业务验收。 |
| 动态 Alias | 只使用设备原生内容处理和缓存刷新语义；执行机不自行解析来源，也不新增强制刷新路径。 |
| 缓存 | 不要求来源、有效期和所有权等专用证据；设备原生缓存语义不由工作流替换。 |


```yaml
components:
  opnsense:
    inputs:
      aliases: opnsense/aliases.yml
      dnat: opnsense/dnat.yml
    files:
      inventory: opnsense/inventory.yml
      request: opnsense/request.yml
```

以下是实际在线 plan 的命令结构；synthetic 文件只展示配置格式。离线选择检查见
[示例说明](../examples/opnsense-workflow/README.md)：

```sh
iaas run --runtime-config runtime.json \
  --environment docs/examples/opnsense-workflow/environment.yml \
  --engine local --component opnsense --operation plan \
  --scope firewall --output ./opnsense-plan
```

该示例使用文档保留地址，不包含设备凭据，不证明 API 连通或设备状态。实际
`plan` 通过 `OPNSENSE_API_KEY`/`OPNSENSE_API_SECRET` 读取设备观察并产生私有
`candidate.json`。调用方保存候选 SHA-256 后，apply 只接收该候选，不重新加载
desired inputs。apply 的 options 必须包含 `candidate_sha256`、`execution_id` 和
`activation_check`，可选 `check_mode: true|false`；三者绑定相同候选和目标；`activation_check` 还必须记录
`checked_no_pending: true` 与 `serialized: true`。launcher 要求
`--execution-id` 与新 output 目录 basename 相同，并核对 runtime discovery 的
回显。调用方负责生成新的执行身份并维持整个保存/激活窗口的串行化；这些字段
不是分布式锁或跨主机防重放注册表。

结果中的 save、activation、configuration 和 active 分别记录不同事实；默认成功基础是
保存、配置回读和原生激活成功。Alias、Gateway、Group 原生返回无法证明的内部子动作
固定输出不可关闭 stderr 警告并写入 result，但不停止默认依赖阶段。
需要 PF、route-to、接口组或 runtime 深度事实时，显式运行 inspect；结果独立记录，
不改写原 apply。所有结果的业务验收保持 `not_performed`，确认范围见上表。

可选深度核查命令：

```sh
PYTHONPATH=automation/src uv run python -m iaas_automation.opnsense_workflow.inspect \
  --inventory INVENTORY --candidate CANDIDATE --output OUTPUT
```

该命令只读候选选中对象并生成新的私有 JSON 报告；不保存、不激活、不刷新内容，
也不证明内部子动作完成或业务连通性。`--inventory`、`--candidate` 和 `--output`
必须分别指向匹配的 inventory、已审查候选和新输出路径。

显式恢复按以下步骤执行：

1. 检查失败执行的私有 result/recovery，核清部分保存和后态；不整批重试旧 apply。
2. 新环境入口的 `files` 指定 inventory、request、recovery，移除 desired inputs；
   request 选择本次恢复身份，并显式声明需要的 managed/adopt。
3. 执行 plan，审查新的反向候选及 SHA-256；原结果未知、后续漂移或
   `manual_required` 均会拒绝自动恢复，须先人工核清。
4. 使用新 execution_id、全新 output 目录和新的共享激活检查结论执行 apply，
   再核对配置、可支持的活动项和调用方业务路径。没有自动回滚。

完整的合成文件见 [request/candidate/result/recovery 示例](../examples/opnsense-workflow/README.md)。
它们包含虚构目标和 runtime digest，不可直接用于现场执行。

能力限制、软件证据和消费前提见 [交接说明](../../openspec/changes/archive/2026-09-19-add-opnsense-config-workflow/acceptance.md)。

## 2.6 有界只读诊断

使用同一环境清单和调用方注入的 API 凭据。必须明确一个 `opnsense` 组内的 inventory host，
不能传组名、通配符或 Ansible `--limit`；工具先在控制端校验目标、请求和输出路径。
`ENVIRONMENT_DIR`、`OUTPUT_DIR` 和请求路径均使用绝对路径。

```sh
make opnsense-diagnose \
  OPNSENSE_TARGET=your-firewall-inventory-host \
  OPNSENSE_DIAGNOSTICS_REQUEST=/absolute/diagnostic-request.json
```

直接 Ansible 使用相同校验（先在仓库执行 `uv sync --locked --dev`）：

```sh
ANSIBLE_CONFIG="$PWD/automation/ansible/ansible.cfg" uv run ansible-playbook \
  -i "$ENVIRONMENT_DIR/ansible/inventory.yml" \
  automation/ansible/playbooks/opnsense/diagnostics.yml \
  -e '{"opnsense_diagnostics_target":"your-firewall-inventory-host","opnsense_diagnostics_request":"/absolute/diagnostic-request.json"}'
```

请求为 JSON 或 YAML 映射，固定 `schema_version: 1`。三种示例见
`tests/fixtures/opnsense-capabilities/diagnose-*.json`，地址和规则身份须由调用方替换。

| kind | 必需选择条件 | 可选选择条件 |
| --- | --- | --- |
| `alias` | `alias_name` | 无；分别报告配置项数量和实际表项观测。 |
| `rule_logs` | `rule` 或 source/destination IP | `rule` 使用 scope＋slug 或 UUID；可叠加 IP、protocol、端口、interface、since/until。 |
| `states` | source/destination IP | protocol、source_port、destination_port。 |

地址字段为 `source_ip`、`destination_ip`，只接受 IPv4/IPv6 字面地址；条件按 AND 组合。
protocol 使用小写 `tcp/udp/icmp/icmpv6`，端口为 1–65535 的整数且必须配 TCP/UDP。
日志时间为带 `Z` 的 UTC RFC3339 字符串；同时提供 since/until 时必须顺序正确。
`limit` 默认 100，范围 1–1000；未知字段和不适用的选择条件会被拒绝。

默认控制台仅输出带版本、时间、目标、选择条件、计数和覆盖范围的摘要，不输出表项、日志、状态记录或 URL。
`ok` 的零匹配仅针对实际检查的可评估样本；`unsupported` 和 `error` 都返回非零退出码，观测计数为 null。
缺少必需字段、规则关联或无法区分后端失败的空数据不会被解释为零流量。
固定版本的 `query_states` 返回 `current: 0` 时属于错误页；其他无法确认的空观测标为 unsupported。

API 连接/read timeout 分别为 5/15 秒，每个响应最多 2 MiB、一次操作累计最多 8 MiB，最多查询 5 页。
日志只读取有限的近期样本，不是历史日志检索；时间缺少时区时不能做 UTC 过滤。
状态按返回的 src_addr/dst_addr 精确匹配，NAT、接口、gateway、route-to/reply-to/dup-to 和 rtable 按接口实际返回标记可用性，不推断完整路径或最新规则是否生效。
配置保存、表项存在和 URL 定期刷新成功是不同事实；接口未提供的更新时间保持不可用。

需要详情时，在请求中显式设置 `include_details: true`，同时传入
`OPNSENSE_DIAGNOSTICS_OUTPUT=$OUTPUT_DIR/runtime/opnsense-diagnostics/fw/result.json`；直接 Ansible 对应
`opnsense_diagnostics_output`。目录为 `0700`、文件为 `0600`，禁止符号链接、越界或覆盖请求、清单及手写输入。
只指定输出路径不会启用详情，未启用时不创建详情文件。

所需设备权限按操作选择：别名配置使用 `Firewall: Aliases`，表项使用 `Diagnostics: PF Table IP addresses`，
日志使用 `Diagnostics: Logs: Firewall: Live View`；规则选择还需要 `Firewall: Rules [new]` 和
`Diagnostics: Firewall sessions`，状态查询使用 `Diagnostics: Show States`。
其中部分设备权限也包含写操作，但本诊断入口只调用固定的只读操作，不刷新别名、不激活规则、不清理状态。
权限、字段和限制以 core 26.1.11 源码为基线；软件测试不代表某台设备或流量路径已经验收。

## 2.7 验收与停止

验收至少包括：API 连通、目标对象身份与顺序正确、管理路径保持可达、DNAT/1:1
NAT/Groups 的保存与激活结果可区分、所需的 PVE/VM/Registry/DNS 路径经过实际测试，
以及未出现未解释的规则阴影或网关监控告警。API 调用返回成功不等于数据面一定可用；
离线测试、check/generate 或受保护的只读响应都不能单独宣称设备写入和现场资格完成。

若管理通道、核心 DNS/路由、既有关键服务或回退路径异常，立即停止后续 PVE/
VM/K3s 变更，保留 export 和变更记录，通过本地控制台恢复。不要批量删除
规则、临时设为默认网关或以未审查的 raw API 请求绕过本工作流。


### 调用方生成的标准声明与校验上下文

Alias/Rules 可手写，也可由调用方从其维护的输入确定性生成；资源字段、稳定身份、显式状态与增量管理规则相同。设备导出必须经审查并转换为标准声明，不能直接用于部署。通过原有 `opnsense_alias_source` / `opnsense_filter_rule_source` 选择文件；省略对象不代表删除。Gateway/VIP 仍引用原基础源。DNAT、1:1 NAT 和 Groups 通过各自 source 变量选择标准文件；SNAT 的四个命名仍是未实现占位。

规则文件可附带 `opnsense_filter_rule_context`，仅含 `interface_networks`（接口到 CIDR 列表）和 `aliases`（标准别名列表）。反向匹配只能有一个目标；反向 deny 的入口网络保护只接受静态覆盖证据，按 inet/inet6/inet46 分别检查。域名、URL Table 和未知外部成员本身不构成静态证据；未知外部引用仍按既有在线解析合同处理。上下文与所选别名声明冲突时拒绝，离线接受不证明现场事实有效。

调用方可以通过 `PYTHONPATH=automation/src uv run python -m iaas_automation.opnsense_validation --vars-dir DIR` 校验原有四文件集，或用 `--resource dnat|one-to-one-nat|interface-groups --file FILE` 显式校验新增资源，再用 runtime_config 的 check/generate 入口生成文件。Ansible 加载后的复验也位于凭据访问前，不把字符串转换成整数或布尔。配置保存与激活仍是不同结果，不承诺跨资源事务；有引用时通常先处理 Groups/别名，再处理引用它们的 NAT/过滤规则，删除则反向进行。执行授权、阶段编排及恢复决策由调用方负责。
