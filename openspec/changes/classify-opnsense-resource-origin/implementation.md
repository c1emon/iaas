# 实现与验证边界

## 分类依据

适配沿用固定 Collection 26.1.11 和 OPNsense 26.7.3 的配置模型，不新增固件探测或 PF 枚举。

- Alias 原生 `internal` 类型提供系统内置依据；固定 `core.json` 防护表还要求静态 UUID 与完整固定字段匹配。用户 `external` 及 URL 等动态内容对象仍与系统来源分开；系统引用只在完整成员能够证明地址／端口角色时提供，空成员或无法解释的成员不虚构支持。
- Firewall Group 的静态子项通过固定模型、静态 UUID、名称、序号、说明及归一化后的空成员共同识别；原生未选择的 selector 仍属于空成员。名称相同不足以分类；API 不输出可直接使用的 virtual／readonly 来源标记。
- Gateway 缺地址或转换失败不证明只读，保留 unknown。普通持久化模型的可编辑声明仍需所有权与配置表达检查。
- 来源、管理能力、配置表达与数据性质独立输出；依据使用受控标识，不保留原始响应作为证据。

固定版本源码：[Alias 模型](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/Alias.xml)、[AliasField](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/FieldTypes/AliasField.php)、[GroupField](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/FieldTypes/GroupField.php)、[ArrayField](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Base/FieldTypes/ArrayField.php)。

## 合同与消费

默认视图隐藏确认的系统／派生只读或来源管理项，未知项和显式选择仍展示。read 的 `include_system` 仅展开视图；完整观察始终独立保存。候选、结果及恢复升级至 v3，旧材料需要重新读取和规划，request 保持 v1。

计划、执行重读及恢复均检查独立管理能力；引用证据不代替配置或管理权限。创建后使用实际分类回读，不预先虚构证据。不存在对象不能申请激活恢复。

infra-ops 的消费方式见 [操作说明](../../../docs/operations/02-opnsense.md)；本次不修改其站点策略或部署版本。

## 验证

用户另行授权在线只读测试，使用本分支源码与现有 1Password 临时注入；设备原始材料保存在仓库外私有目录，不纳入提交。

离线覆盖 reader／转换、默认与全量视图、runtime／local 契约、依赖与分类漂移、候选准入及原生恢复代表路径；最终相关测试 677 项通过。类型、lint、导入边界及 OpenSpec 严格校验通过。

2026-09-21 在线只读复测通过：七类配置共枚举 79 项，默认展示 62 项，`--include-system` 展示 79 项，两次完整观察一致。Alias 26 项中 14 项确认为系统项、12 项普通声明可表达；3 项静态 VPN 组确认为派生只读；2 项未知 Gateway 继续显示。35 项 Filter、6 项 DNAT、6 项 VIP 与空 1:1 NAT 集合均完整读回。显式系统身份仍可展示。

追加限定字段核对确认：两个未知 Gateway 均关联 WAN，协议族分别为 IPv4／IPv6，配置地址为空，IPv6 描述指向 DHCP。该观察支持动态 WAN 网关解释，但不证明对象来源或独立删除／重建能力，因此未将其改判为系统只读。

在线观察提供了 3 项系统组引用描述。系统 Alias 的本次原生成员为空，未生成引用角色证据；分类识别不自动证明它们可用于现有规则引用。该能力仅在完整成员证明角色的离线代表例中验证，不扩大为所有系统 Alias 支持。

实测发现并修正了两处适配差异：静态组的空成员采用未选中的 selector；四个防护 Alias 使用 `external` 类型，需结合 [固定 core.json](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/static_aliases/core.json) 的完整字段与原生静态身份分类。未知插件静态项不获得独立管理能力。

GitNexus 已刷新并执行变更分析；共享计划／执行路径风险为 HIGH／CRITICAL，已用上述定向回归覆盖。图的流程构建存在预算裁剪，未出现的流程不被解释为无影响。

未执行设备配置写入、发布或业务验收。示例 JSON 使用离线测试替身生成，不是设备执行证据。
