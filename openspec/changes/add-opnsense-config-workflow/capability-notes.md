# OPNsense 只读能力核对

日期：2026-09-19。范围：固定 `oxlorg.opnsense` Collection commit
`1423500c29f88da9ba8147a23fc64006cf464159`（仓库清单中的 pinned source）。本说明只记录源码和合成响应证据；没有访问设备、读取凭据或宣称现场资格。

## 支持矩阵

| 标准类别 | Collection `list` target | 固定读取模型 | 稳定身份 | 规范化字段边界 |
| --- | --- | --- | --- | --- |
| aliases | `alias` | `alias.aliases.alias` | `[name]` | name/type/content/description/enabled/updatefreq_days |
| vips | `interface_vip` | `vip.vip` | `[address, interface]` | description/interface/address/bind/expand |
| gateways | `gateway` | `search_gateway` + `get_gateway` | `[name, gateway]` | PBR 字段和数值阈值，保留 address family |
| filter-rules | `rule` | `filter.rules.rule` | `[iaas:opnsense:filter:scope:slug]` | 标准规则字段；description 仅用于还原身份 |
| dnat | `nat_destination` | `DNat.rule` | `[iaas:opnsense:dnat:scope:slug]` | DNAT 字段、嵌套 source/destination 和端口 |
| one-to-one-nat | `nat_one_to_one` | `filter.onetoone.rule` | `[iaas:opnsense:one-to-one-nat:scope:slug]` | IPv4 NAT/BINAT 字段和反向标记 |
| interface-groups | `rule_interface_group` | `group.ifgroupentry` | `[name]` | members/gui_group/sequence/description |

上述模块分派和 `API_KEY_PATH` 来自本地固定 Collection 的
`plugins/modules/list.py` 以及各资源的 `plugins/module_utils/main/*.py`。Reader
只接受这七个常量 target；它不接受任意 module/controller/path/body，也不调用
save、reload、reconfigure、state 清理或 Alias 内容刷新。

## 读取完整性和字段结论

固定 transport 仅调用 Collection 对应的配置读取路径，响应大小限制为单响应
2 MiB、同一 Reader 会话 8 MiB，分页单页最多 1000 行且最多 5 页。Collection 已规范化的
完整列表和固定 `rows/current/rowCount/total` 分页均可读取；页号、总数、行类型、
重复身份、必要字段或详情缺失时返回 `incomplete`/`failed`，不会把空集解释为
不存在或 no-change。

Reader 的 `normalize_desired` 复用现有七类的 provider 默认语义，并仅补充可表达的
布尔值、空字符串和稳定列表顺序；完整声明的跨资源 validator 仍在 core 入口执行。差异比较使用规范字段，忽略 UUID、计数器、
时间戳和动态 Alias 成员；URL/DNS Alias 的声明 content 与运行时表项仍保持不同
观察范围。无法由标准 schema 无损表达的已识别对象返回 `configuration: null`、
稳定 `identity`、有界 `references` 及 `recovery: manual_required`。

规则/转换的 `source_net`、`destination_net` 和端口集合在比较前统一成稳定 token
列表；原生 `source.network` 映射为 `source_net`，数字字符串只在 Collection 的
整数字段上转换，select/select-list 和反向布尔按 `simplify_translate` 语义处理。
非托管规则不以普通 description 冒充身份：有 uuid 的对象使用 `native:<uuid>` 并
保留 unknown/manual recovery；没有稳定 uuid 的对象使该资源枚举保持 incomplete。

## 引用、接口和激活边界

filter/NAT 的 alias、interface-group、gateway 引用以稳定标签输出；未知配置仍
保留这些引用，供 plan 在写前拒绝缺失或不完整依赖。固定 OPNsense
`firewall/group/get_item` 的 `group.members` 字段选项给出逻辑接口键；固定
26.1.11 的 `Firewall/FieldTypes/InterfaceField.php` 明确排除 type=group。
`diagnostics/interface/get_interface_names` 返回原始网卡名，不能证明 lan/wan 存在。
选项不可用时 `coverage.interfaces: unavailable`，不把任意字符串视为已存在接口。

激活路径对照固定 [OPNsense core 26.1.11](https://github.com/opnsense/core/tree/26.1.11)：

- Filter/DNAT/OneToOne 的 `FilterBaseController::applyAction` 返回
  `configdRun('filter reload skip_alias')`；`service/modules/actions/script.py` 的
  script 成功为 `OK`、失败为 `Error(n)`。VIP 同样返回同步 configd 状态的小写值。
  仅成功状态视为 `confirmed`；不替代业务验收。
- Alias、Group、Gateway handler 在 configd 调用后无条件返回 `ok`，故仅
  `unconfirmed`。静态地址 Alias 可由独立 PF table 核对补充确认；其他未确认
  激活会使本次 apply 失败并停止依赖阶段，不会悄悄继续。
- 独立活动核对不支持的类别仍记录 `unsupported`；同步激活已经确认且配置一致时，
  总体结果为 `completed_with_unverified`。固定提供者没有通用 pending-change
  证明，apply 必须使用绑定本次目标、候选摘要和 execution_id 的调用方检查结论。

active_check 只对 host/network Alias 使用固定 diagnostics
`firewall/alias_util/list/<alias>` 的完整 PF table 成员集合与期望 CIDR 做精确比较；
截断、空表删除证明、port/networkgroup 以及 URL/DNS/dynamic Alias 均返回
`unsupported`/`incomplete`，不会把“接口可读”升级成活动已验证。其他六类保留
saved-configuration-only 的 unsupported 边界。

## 代表性软件证据

`tests/python/test_opnsense_workflow_reader.py` 覆盖七类 target 的合成读取、稳定
身份、字段规范化、分页边界、重复匹配、缺少字段的 manual recovery、未知字段的 manual recovery、
显式目标及没有写方法的只读边界。测试没有启动 Ansible 写模块，也没有连接设备。

固定 Collection 仍要求运行时使用仓库锁定版本；若某一设备响应缺失必要详情或
提供者端点返回 unsupported，工作流保留 unknown/incomplete 结果并在 apply 前停止。
