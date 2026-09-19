# OPNsense 激活确认能力核定

日期：2026-09-20。本文只核对源码和仓库内固定 Collection 的接口边界，不访问设备、不读取凭据、不宣称现场资格。

## 核定基线

- Collection 基线采用仓库既有固定提交 [`1423500c29f88da9ba8147a23fc64006cf464159`](https://github.com/O-X-L/ansible-opnsense/tree/1423500c29f88da9ba8147a23fc64006cf464159)。本地物料的 Galaxy 元数据为 `oxlorg.opnsense` `26.1.11`；这只是 Collection 包版本，不是目标设备版本。
- 目标设备源码固定为 OPNsense core [`26.7.3`](https://github.com/opnsense/core/tree/26.7.3)。以下结论只绑定这一源码目标，不能外推到其他 OPNsense 版本。
- Collection 的 Alias、Gateway、接口组模块都通过 [`BaseLogic._base_reload`](https://github.com/O-X-L/ansible-opnsense/blob/1423500c29f88da9ba8147a23fc64006cf464159/plugins/module_utils/base/logic.py#L425-L440) 调各自 controller 的 `reconfigure`。固定 Collection 的 `raw` 模块可以接受任意 API 路径，但这不是已核定的只读能力，也不允许用它绕过本说明的固定端点边界。

### 版本闸门

26.7.3 的 [`FirmwareController::statusAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Core/Api/FirmwareController.php#L92-L123) 从 `firmware product` 读取产品资料；[`product.php`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/firmware/product.php#L30-L45) 读取 `/usr/local/opnsense/version/core`，而 [`core.in`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/version/core.in#L1-L41) 明确提供 `product_version` 字段。因此固定源码支持一个只读版本事实：通过该 controller 的 `status` 读取并检查返回的 `product.product_version`（或在错误/缺失时返回 unknown）。

当前 workflow reader 已固定使用 `GET /api/core/firmware/status`，读取 `product.product_version` 后与精确值 `26.7.3` 比较；这确认了软件合同中的版本字段，不确认现场设备已经通过版本闸门。该只读路径在 26.7.3 的 ACL 中归属 [`System: Firmware`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Core/ACL/ACL.xml#L506-L514)，其 pattern 是 `api/core/firmware/*`，源码没有单独的“firmware version read-only”权限名。因此调用方必须按已有 ACL 授权取得该状态，不能把权限名描述成窄只读权限。设备版本读取失败、权限拒绝、响应不完整或不是精确的 `26.7.3` 时，依赖本说明的操作必须保持 blocked。版本 probe 不能触发 firmware probe、升级检查或其他写操作。

## 按操作的能力矩阵

| 操作 | 已核定的只读事实 | 本次动作完成证据 | 结论 |
| --- | --- | --- | --- |
| 静态 host/network Alias | 配置可由 Collection 的 Alias `get` 读取；对启用对象，`firewall/alias_util/list/<name>` 可返回当前 PF table 成员，完整响应时可比较 IPv4/IPv6 地址语义。 | `reconfigure` 没有统一完成关联；同次 refresh 无 messages 加上 PF table 精确匹配，只能确认当前态，不能回溯未观测的 reload/template/cron 链路。 | 静态 table 当前生效可以确认；写入动作完成仍 blocked，新增/删除消费者或整条同步链仍须单独标注 `unconfirmed`。 |
| port Alias | 配置和 Alias 类型可读；PF table 读取只返回地址项。26.7.3 另有通用的 `pf_statistics` 规则统计路径，可看到 pfctl 原始规则文本和计数。 | 规则文本本身可带 `label "<uuid>"`；固定 reader 已通过 `pf_statistics/rules` 使用选中配置规则 UUID 做关联，并定向解析 `on`、`proto`、`from/to`、端口表达式及 `route-to`。这仍是当前 loaded-rule 观察，不是 reconfigure 完成关联。 | port 当前检查可独立报告；本次 native reconfigure 的完成证据仍缺失，不应阻止该只读检查。 |
| 动态 Alias（URL/DNS 等） | 配置中的来源、类型和更新频率可读；当前 Alias table 可在端点可用时读取。 | `refresh_aliases` 由脚本处理依赖链、解析/下载并加载 table；源码存在内部 cache/resolve 处理，但审阅到的固定读取路径未逐对象返回来源、缓存时间、有效期、解析/下载结果或加载完成结果；workflow 也不能观察 `/var/db/aliastables`。 | 新增、来源变化、重新启用和缓存复用的必要证据缺失，动作 blocked。这是当前 adapter/公共合同的证据缺口，不是“上游完全没有任何动态 API”的结论。 |
| Alias 禁用/删除 | 配置列表、活动 table 名称和单表内容可分别读取；可区分部分对象是否仍存在。 | Alias reconfigure 仍只有无关联 `ok`；缺少统一的退役完成结果，缺表、空表和读取失败不能由同一个响应安全区分。 | 只有在明确的当前状态检查中报告观察结果；作为必要动作确认时 blocked。 |
| PBR Gateway | `routing/settings/search_gateway` 返回配置，并同步调用 `interface gateways status`，可读接口、下一跳、监控状态、loss、delay、stddev 等运行信息；26.7.3 还提供 `GET /api/diagnostics/interface/get_routes` 读取当前系统路由表。 | 固定 reader 对完整分页的 `search_gateway` 保留配置/runtime 字段，并按显式 monitor-host 需要读取路由快照；`reconfigure` 只调用 `interface routes configure` 并无条件返回 `status=ok`，仍无本次动作关联。`route-to` 消费者关联由独立 PF 规则观察合同提供。 | 配置、gateway monitor 和系统路由快照可用；PBR Gateway 必要动作确认 blocked。 |
| 接口组 | `firewall/group/get`/search 可读保存的名称、成员、GUI 标志、顺序和描述；`diagnostics/interface/get_interface_config` 可读 kernel/interface config，`interfaces/overview/interfaces_info` 可把 `config.identifier` 映射到设备；Filter 配置可提供规则引用。 | Group reconfigure 依次调用接口注册、接口选项缓存刷新和 filter reload，但丢弃这些调用的返回值并无条件返回 `ok`；上述当前读路径没有完成代数或 loaded rule 消费确认。 | 保存配置、当前 kernel 组/接口映射和部分引用可读；接口组注册、成员生效和 filter reload 的必要动作确认 blocked。 |

## 证据和硬缺口

### Filter/NAT/VIP 同步激活与 ACL

Filter/NAT 的同步激活有 26.7.3 原生 controller 证据：[`FilterBaseController::applyAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/FilterBaseController.php#L302-L309) 对 POST 调用 `configdRun('filter reload skip_alias')` 并返回后端结果；[`DNatController`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/DNatController.php#L34-L38)、[`OneToOneController`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/OneToOneController.php#L31-L34) 和 [`SourceNatController`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/SourceNatController.php#L32-L35) 继承这条路径。VIP 的 [`VipSettingsController::reconfigureAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Interfaces/Api/VipSettingsController.php#L230-L237) 调用 `interface vip configure` 并返回规范化后的后端结果；对应 action 定义为 script，脚本 runner 对退出码返回 `OK` 或 `Error (n)`（[`script.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/service/modules/actions/script.py#L32-L46)）。这些是同步 provider action evidence，不是跨对象的动作 ID 或运行时业务确认。

源码 ACL 名称和 API pattern 的核对如下；名称是权限边界，不能从名字推断现场调用已被授予：

| 能力 | 26.7.3 ACL 名称 | API pattern / 说明 |
| --- | --- | --- |
| 版本 status | `System: Firmware` | `api/core/firmware/*`；包含 firmware 管理面，源码没有独立只读版本权限 |
| 系统路由快照 | `Diagnostics: Routing tables` | `api/diagnostics/interface/get_routes*` |
| Gateway 配置/status | `System: Gateways` | `api/routing/settings/*`、`api/routes/gateway/status` |
| Alias 配置 | `Firewall: Alias: Edit`、`Firewall: Aliases` | `api/firewall/alias/*`；后者覆盖 search/list/get/export |
| Alias PF table | `Diagnostics: PF Table IP addresses` | `api/firewall/alias_util/*` |
| PF 规则统计 | `Diagnostics: Firewall statistics` | `api/diagnostics/firewall/pf_statistics/*` |
| 接口组 | `Firewall: Groups` | `api/firewall/group/*` |
| Filter/NAT | `Firewall: Rules [new]`、`Firewall: NAT: Source NAT`、`Firewall: NAT: 1:1`、`Firewall: NAT: Destination NAT` | `api/firewall/filter/*`、`api/firewall/source_nat/*`、`api/firewall/one_to_one/*`、`api/firewall/d_nat/*` |
| VIP | `Interfaces: Virtual IPs: Settings` | `api/interfaces/vip_settings/*` |

对应官方 ACL 源码分别见 [`Core/ACL.xml`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Core/ACL/ACL.xml#L106-L190)、[`Core/ACL.xml` firmware/gateway](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Core/ACL/ACL.xml#L506-L529)、[`Diagnostics/ACL.xml`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Diagnostics/ACL/ACL.xml#L30-L36)、[`Firewall/ACL.xml`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/ACL/ACL.xml#L1-L29) 和 [`Interfaces/ACL.xml`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Interfaces/ACL/ACL.xml#L16-L22)。

### `pf_statistics` 规则关联和最小解析合同

26.7.3 的 [`pfStatisticsAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/FirewallController.php#L340-L346) 将 `api/diagnostics/firewall/pf_statistics/rules` 的 section 传给 `filter diag info`；[`actions_filter.conf`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/service/conf/actions.d/actions_filter.conf#L120-L124) 调用 [`pfstatistics.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/pfstatistics.py#L89-L108)。该脚本返回的 JSON 形状是 `rules -> filter rules|nat rules -> {rule_text: counters}`：`rule_text` 是字典 key，JSON 没有独立的 `label`、`uuid`、`on`、`proto`、`source` 或 `destination` 字段；计数值主要是从 bracket 行提取的统计项。

规则文本仍足以支持一个固定、定向的只读 parser。`pfctl` 规则文本按 OPNsense 生成的 `label "<uuid>"` 携带规则 UUID；配置侧 [`FilterController::searchRuleAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/FilterController.php#L97-L106) 明确以 model key 返回 `uuid`，因此可以用 UUID 对选中的 filter rule 做关联。[`list_rule_ids.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/list_rule_ids.py#L25-L39) 还证明活动 label 可映射到描述，但该辅助端点不是 port 检查的必要条件。规则生成器把 port Alias 展开成 PF 宏表达式（[`filter.inc`](https://github.com/opnsense/core/blob/26.7.3/src/etc/inc/filter.inc#L558-L606)），所以 parser 应保留原始端口表达式并只在语法完整时归一化。

NAT consumer 的 native UUID 关联存在硬能力缺口：`pf_statistics` 的 `nat rules` 仍只是 `pfctl -vvsnat` 原始文本；26.7.3 的 [`ForwardRule`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/library/OPNsense/Firewall/ForwardRule.php#L39-L57) 与 [`DNatRule`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/library/OPNsense/Firewall/DNatRule.php#L37-L68) 输出定义没有 `label`。自动生成的 filter 规则若没有 label，会由 [`Plugin::registerFilterRule`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/library/OPNsense/Firewall/Plugin.php#L260-L272) 使用计算 hash，而不是 DNAT/1:1 NAT model UUID。因此 port/group 对相关 `dnat` 或 `one-to-one-nat` consumer 只能报告 `unsupported_nat_consumer_identity`，不能把缺少 native identity 当成无消费者或成功关联。

最小固定合同应限定为：

1. 仅读取 `filter rules`（需要 NAT 时另行读取 `nat rules`），对每个 `rule_text` 提取 `pf_index`（前导 `@N`，如有）、`uuid`（`label "..."`）、`on` 接口、`proto`（单值或 `{...}`）、`from`/`to` 地址表达式及其紧随的 `port` 表达式；保留原始 `raw_rule` 和 counters。
2. 识别 `route-to`（以及若出现的 `reply-to`/`dup-to`）为原始、平衡括号表达式；不把它误当成 `to` 地址或端口。`on`、协议、源/目标和 route option 缺失或出现无法平衡的 `{}`/`()` 时，结果为 `unresolved`，不能默认为匹配或不匹配。
3. 只以 UUID 将结果关联到选中配置规则；同一 UUID 出现多条 PF 展开规则时返回全部 `pf_index`/raw entries 并按规则聚合，不能按显示顺序猜测。没有 UUID 的内部/自动规则只能作为未关联运行观察。
4. 端口只确认 parser 实际读到的原始表达式（例如 `$PORT_ALIAS`、`{ 80 443 }`、`1000:2000`、`1024 <> 65535`）；Alias 宏未在响应中展开时返回 `unresolved`，不声称端口成员已验证。这样可覆盖选中规则的协议、源/目标端口、`route-to` 和接口观察，同时保持对未识别语法 fail closed。

代表性 fixture（只说明字段合同，不是现场响应）：

```json
{
  "rules": {
    "filter rules": {
      "@42 pass in quick on wan route-to ( wan 192.0.2.1 ) inet proto tcp from any to any port $WEB label \"11111111-1111-4111-8111-111111111111\"": {
        "evaluations": 7
      }
    }
  }
}
```

对配置中 UUID `11111111-1111-4111-8111-111111111111` 的规则，最小结果应为 `pf_index=42`、`uuid` 同值、`on=wan`、`proto=[tcp]`、`src=any`、`dst=any`、`dst_port_raw=$WEB`、`route_to_raw=( wan 192.0.2.1 )`、`evaluations=7`，并保留原始 rule text。该 fixture 不证明现场规则已加载；它只证明固定 parser 的输入/输出边界。

### Alias 完成、动态缓存和 PF

26.7.3 Alias controller 的 [`reconfigureAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasController.php#L305-L323) 依次执行 `filter reload skip_alias`、Filter template reload、`filter refresh_aliases` 和 cron restart。它只将 refresh_aliases 的 JSON `messages` 转成异常，然后返回 `{status: "ok"}`；前三个调用中，reload、template 和 cron 的返回值没有逐项保留，也没有动作标识。这里不能把“没有 action ID”本身当作失败条件：对静态 Alias，`refresh_aliases` 无 messages 加上同次 `list/<name>` 的精确成员匹配，可以作为可信的当前 PF table 完成证据。

当前唯一可用于静态地址活动观察的固定 API 是 [`AliasUtilController::listAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/AliasUtilController.php#L73-L96)，其调用 `filter list table`。对应的 configd action [`list.table`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/service/conf/actions.d/actions_filter.conf#L33-L45) 和 [`list_table.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/list_table.py#L29-L58) 只列 PF table 内容。它不能单独证明 table 是由当前刷新产生，也不返回 dynamic source、处理时点或动作关联信息；但当它在同一个请求序列中与 reconfigure 的无 messages 结果、期望配置成员做精确匹配时，可以确认“当前静态 table 已达到目标状态”，而不是要求额外的执行 ID。

需要保留的具体失败吞路径是：`filter reload skip_alias`、`template reload OPNsense/Filter` 和 `cron restart` 的非空/错误返回在 controller 中都被直接丢弃；`filter refresh_aliases` 只检查解码后的 `messages`，不检查 `status`，而 [`update_tables.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/update_tables.py#L57-L132) 在 XML parse error 等路径可以直接以非零退出而不输出 JSON，或返回仅有 `status: error` 的异常形状。此时 `json_decode` 可能为 null、`messages` 为空，controller 仍可能继续 cron 并返回 `ok`。因此静态 table 精确匹配能补足“当前内容”事实，却不能抹掉这些未观测的链路失败。

缺失返回值的影响要按消费者区分：已有静态 table 的成员替换成功时，忽略 template/reload 返回不必然否定当前 table；但新增/删除 Alias 或新规则消费者依赖 filter reload 的表声明，template 失败可能使 refresh 使用旧的 filter tables 配置，cron restart 失败则影响后续动态周期。故静态 host/network Alias 可以确认当前 PF table，整条 reconfigure 及新旧消费者生效仍为独立的 `unconfirmed`。

动态 Alias 的真实处理路径在 [`update_tables.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/update_tables.py#L57-L137)：脚本为 URL/DNS 等 Alias 处理依赖链，按 `cached()` 或 `resolve()` 取得内容，再将文件和 PF table 对比后 replace。该缓存和文件状态是 OPNsense 本地内部状态；固定 API 没有逐对象暴露 source identity、cache freshness、解析/下载结果或加载完成结果。因此：

- 当前 table 内容相同不能证明本次来源处理完成；
- 旧缓存不能在来源变化后证明新来源已经处理；
- 合法空内容、获取失败和读取不完整不能仅凭 table 不存在或为空区分；
- 不应通过临时改描述、禁用/启用或创建测试规则强制制造内容差异。

端口 Alias 的活动核对需要已加载 PF 规则的协议、源/目标端口角色及范围。26.7.3 的 `list table` 只提供地址集合；Filter controller 的 [`searchRuleAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/FilterController.php#L80-L155) 是保存规则搜索，不能作为 loaded PF rule 展开。另有 [`pfStatisticsAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/FirewallController.php#L362-L368) 对应的 `api/diagnostics/firewall/pf_statistics/*` 路径；其 [`pfstatistics.py`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/scripts/filter/pfstatistics.py#L99-L120) 从 `pfctl -vvsrules` 解析原始规则文本和计数。该路径没有结构化端口字段，但规则 key 可按前述合同提取 UUID、协议、接口、源/目标端口原文和 route option；固定 reader 现在已消费该路径并完成 bounded UUID 关联/定向解析。它仍只证明当前 loaded-rule 观察，不能替代 native reconfigure 完成证据。

### Gateway

Gateway controller 的 [`reconfigureAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Routing/Api/SettingsController.php#L35-L47) 调用 `interface routes configure` 后直接返回 `ok`。同一 controller 的 [`searchGatewayAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Routing/Api/SettingsController.php#L49-L141) 会读取配置、接口列表和 gateway status，因此可以对接口/下一跳与部分 dpinger 状态做当前观察，但没有本次 reconfigure 的完成关联。

26.7.3 确实存在 [`InterfaceController::getRoutesAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/InterfaceController.php#L157-L184)，即 `GET /api/diagnostics/interface/get_routes`；它调用 `interface routes list -n json`（带 `resolve` 时为 `interface routes list json`），返回当前系统路由的 destination、gateway、netif，并补充接口描述和 id。该路径归属 [`Diagnostics: Routing tables`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Diagnostics/ACL/ACL.xml#L30-L36)。它能补充“当前安装路由快照”观察，但不是本次 `routes configure` 的完成关联，也不提供完整 loaded PBR `route-to` 消费者合同。

因此搜索结果里的 status 仍是 gateway monitor 状态，不是 PBR 规则是否已加载。默认路由、ping 成功或启用 monitor 都不能替代缺少的动作完成证据。`get_routes` 是可用的当前路由快照；route-to consumer 的关联属于当前 PF parser/consumer 观察合同，不能把 parser 尚未覆盖说成上游没有 endpoint。Gateway 适配应在能力规则中保留配置、monitor、系统路由快照的当前观察范围，并对必要确认保持 blocked。

### 接口组

Group controller 的 [`reconfigureAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/GroupController.php#L121-L135) 先调用接口注册，再调用 `filter reload skip_alias`，但两者返回值均未进入响应。其重命名路径也调用同一个注册流程。注册实现位于 [`ApiControllerBase::runInterfaceRegistration`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Base/ApiControllerBase.php#L406-L415)，其中 `interface invoke registration` 和 `!interface list assign-opts` 的结果同样被丢弃。

当前只读路径包括 [`InterfaceController::getInterfaceConfigAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Diagnostics/Api/InterfaceController.php) 的 `GET /api/diagnostics/interface/get_interface_config`（kernel/interface config）以及 [`OverviewController::interfacesInfoAction`](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Interfaces/Api/OverviewController.php) 的 `GET /api/interfaces/overview/interfaces_info`（`config.identifier` 到 device/interface 映射）。这些路径能补充当前态事实，但没有 group completion 或 filter consumer 完成关联。保存的 `ifgroupentry` 成员不等同于运行中接口组已注册；配置规则引用也不等同于 loaded filter rule 已使用新成员。没有新增 SSH、插件、任意 raw endpoint 或设备权限前，接口组注册和 reload 的必要确认能力保持 blocked。

## 对实施的准入结论

1. Filter/NAT/VIP 的既有同步激活可以继续使用其原生同步返回作为 provider action evidence；这不提升 Alias、Gateway 或 Group 的 `ok` 响应。
2. 静态 host/network Alias 在同次 reconfigure 的 refresh 无 messages、配置期望成员与 `list/<name>` 精确匹配时，可以记录为“当前 PF table 已确认”；不能把它扩展成 filter reload/template/cron 全链路完成。动态 Alias、Gateway、Group 仍按各自缺失的完成事实记录为 `accepted`/`unconfirmed`，首写前若其动作是必要前置且没有其他已核定完成证据，必须零写入并返回 actionable blocked。
3. 静态 host/network Alias 的精确 PF table 匹配可以与同次无 messages 结果共同确认当前目标状态；它仍不能追认未观测的 reload/template/cron 分支或历史动作。Gateway 的部分 status/路由快照、Group 的保存配置仍属于独立当前状态观察，不能替代动作完成证据。
4. 版本读取必须是只读且精确检查 `product.product_version == 26.7.3`；缺失、权限拒绝、响应不完整或不同版本均为 unknown/blocked。没有设备访问，本说明只确认源码存在该事实通道，不声称现场已通过版本闸门。
5. 补足上述硬缺口需要新的受审查只读适配、权限或 OPNsense 端能力，超出本 task 的源码核定范围；在获得独立授权前不引入 SSH、插件、补丁、任意 endpoint 或新权限。
