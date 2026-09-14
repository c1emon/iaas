# OPNsense DNAT、1:1 NAT 与接口组通用管理

## Why

iaas 当前只接入 Alias、VIP、Gateway 和 Filter Rules；DNAT 是主动失败的占位，1:1 NAT 和接口组虽有上游模块，也没有标准管理入口。需要在本轮接入两类 NAT（DNAT、1:1 NAT）和独立 Groups 能力，让调用方用标准资源组合环境配置，而非复制设备 API 实现。SNAT 因上游读取兼容性问题延期，先保留后续所需命名和设计位置。

## What Changes

- 在一个 change 中统一设计 DNAT、1:1 NAT 的身份、校验、增量执行、应用和恢复约定，各自保留独立字段、文件与目标入口。
- 增加 Firewall 接口组的名称/成员管理和必要引用校验；不是账户用户组，不是 Categories。
- 固定包含 DNAT 的完整上游 Collection commit，完成本轮三资源（两类 NAT 和 Groups）兼容评估；不跟随浮动 latest。
- 保留旧四类输入和默认目录校验行为；新增三类资源必须显式选择，不自动发现或接管设备对象。
- 整批离线及 Ansible 加载后校验先于凭据；将保存、应用、部分失败与恢复结果分别报告。
- runtime 仅接入离线 check/generate；写入使用三个明确的直接 Ansible playbook 和源文件参数，不新增 launcher apply。Groups 引用以最小改动衔接现有过滤规则/上下文校验，不放宽 VIP/Gateway 物理接口约束。
- present 完整管理合同内字段，省略可选字段清除旧值或恢复合同默认；DNAT 翻译端口按原生限制拒绝字面范围。
- 软件验收、运行时发布、调用方迁移及设备验收分别记录，不以本 change 自动触发现场操作。

SNAT 延期预留：后续仍使用 `snat.yml`、`opnsense_snat_rules`、`manage-snat.yml` 和 `opnsense_snat_source` 命名；本轮不注册 `snat` resource、不加载或执行 SNAT，也不将 SNAT 计入验收或已实现能力。延期原因和后续准入条件保留在 [design.md](design.md) 的延期设计中。

## Capabilities

### New Capabilities

- `opnsense-nat-management`: 两类 NAT 的公共生命周期、可选接入和隔离合同。
- `opnsense-dnat-management`: 目的 NAT、逐规则反射及关联过滤生命周期。
- `opnsense-one-to-one-nat-management`: 一对一 NAT/BINAT 的独立地址映射合同。
- `opnsense-interface-group-management`: 接口组身份、成员及引用保护。

### Modified Capabilities

- `opnsense-mutation-input-validation`: 两类 NAT 与接口组显式加入受支持资源及统一写前校验，保留旧输入兼容性。

## Impact

- 预期涉及 Collection 固定源、两类 NAT 和 Groups playbook、通用 validator、runtime 资源分派、测试及通用手册；不建设一个接受所有 NAT 字段的万能模型。
- 当前固定版本 26.1.11 已含 1:1 NAT、接口组；DNAT 在 `1423500c29f8` 合入，仍标为 unstable，完整 SHA 和本轮三资源在目标 API 上的行为需实施阶段核对。SNAT 虽有命名和延期设计，但不属于本轮 active capability。
- **iaas**：通用低层资源、固定提供者、必要字段/引用校验、精确增量执行。**infra-ops**：站点地址/端口/接口、服务意图、策略组合、全局设置决策、对象接管、批次及恢复。两类 NAT 统一建设不意味着 iaas 自动推导 DNAT→SNAT→过滤规则组合；SNAT 仍由后续 change 单独接入。
- 不包括 SNAT 实现、Categories、NPTv6、全局反射开关、出站 NAT 自动/混合/手工模式切换、nginx/DNS/代理后端、完整设备配置导入或未声明对象清理；相关站点前提由 infra-ops 在迁移阶段处理。
- 保留 change/分支标识 `add-opnsense-dnat-management` 以延续已有规划，标题和内容以本次完整范围为准。当前只调整文档，不改代码、依赖、设备，不发布。

上游依据：[DNAT](https://ansible-opnsense.oxl.app/modules/nat_destination.html)、[1:1 NAT](https://ansible-opnsense.oxl.app/modules/nat_one_to_one.html)、[Groups](https://ansible-opnsense.oxl.app/modules/rule_interface_group.html)、[DNAT PR #430](https://github.com/O-X-L/ansible-opnsense/pull/430)。SNAT 延期设计仍保留其[上游模块命名参考](https://ansible-opnsense.oxl.app/modules/nat_source.html)。
