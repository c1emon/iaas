# 2. OPNsense

本章覆盖 OPNsense 的 API 接入、只读导出、别名、过滤规则、策略路由网关和
IP Alias VIP。它在 PVE 与 VM 创建前定义网络边界，但仓库不自动管理 DNS、
DHCP、物理接口、普通路由、系统升级或稳定 DNAT/端口转发。

## 2.1 准入与责任边界

开始前必须已有：交换机 L2 路径、OPNsense 本地/物理控制台、API 凭据、已审查
的接口标识符、目标网段/端口、回退方案和变更记录。API 配置只管理其声明的
对象；它不会推断“某个 K3s 服务需要开放什么端口”。

`$ENVIRONMENT_DIR/inventory/foundation.yml` 可将 OPNsense 声明为 K3s 前置的
基础服务；该文件只是恢复元数据。健康探针通过 `make foundation-health` 是
在线只读证据，不替代本章的 API 或防火墙规则审查。

当前可管理范围是 API 连通、只读查询/导出/快照、手写别名、IP Alias VIP、PBR
gateway 与 API-backed new filter rules。DHCPv4/v6、RA/PD、WAN/PPPoE、VLAN
interfaces、CARP、Proxy ARP、Other VIP、静态路由、gateway groups、legacy
firewall/management rules、默认防火墙策略、NAT/DNAT 和关键公网入口不在本仓库
管理范围。不要把“能导出”误解为“可回写/可管理”。

## 2.2 配置文件与连接参数

| 文件 | 作用 | 约束 |
| --- | --- | --- |
| `$ENVIRONMENT_DIR/ansible/inventory.yml` | `opnsense` 组、主机别名、API host/FQDN。 | 环境源文件。 |
| `$ENVIRONMENT_DIR/ansible/group_vars/opnsense.yml` | `opnsense_api_url`、`opnsense_ssl_verify`、API key/secret 入口。 | Key/secret 仅用环境变量。 |
| `$ENVIRONMENT_DIR/ansible/vars/opnsense/*.yml` | 声明式期望状态。 | 不从 export 复制回写。 |
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
| `name` | 别名稳定名称。 | 变更前检查所有引用；避免重名。 |
| `type` | `host`、`network`、`port` 等 OPNsense alias 类型。 | 与 `content` 类型一致。 |
| `content` | 地址、网段或端口列表。 | 每个值必须与 alias 类型匹配。 |
| `description` | 人类可读用途。 | 不作为秘密或业务配置载体。 |
| `enabled` | 是否启用。 | 显式布尔值。 |
| `state` | `present` 或 `absent`。 | `absent` 是变更操作，先审查引用。 |

### 过滤规则：`vars/opnsense/filter-rules.yml`

根键为 `opnsense_filter_rules`。`scope` 与 `slug` 是不可变身份；系统生成
`iaas:opnsense:filter:<scope>:<slug>` 描述并以其匹配，禁止手写 `description`。

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `scope`、`slug` | 稳定规则身份。 | 小写数字连字符格式；修改相当于新规则。 |
| `state`、`enabled` | 生命周期和启用状态。 | `state` 只能为 `present`/`absent`。 |
| `sequence` | 规则顺序。 | 推荐 1–99 核心、100–199 策略路由、200–499 特例、900+ 宽泛默认规则。 |
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

仓库精确使用 `oxlorg.opnsense` `26.1.11`。该版本将 API 有时缺失的 `fargw`
处理为可选的 `far_gw`；不得 patch 控制机上已安装的 collection。升级 collection
前，先在隔离环境重新运行语法/离线校验，再确认这个兼容性仍存在。

### VIP：`vars/opnsense/vips.yml`

根键为 `opnsense_vips`。每项必须有 `description`、`interface`、`address`、
`bind`、`expand` 和 `state`。`address` 必须是 CIDR；当前工作流固定 IP Alias
模式。`bind`/`expand` 的含义以 OPNsense API 为准，变更前必须确认该接口和
现有服务不会因 ARP/地址宣告变化失联。

### DNAT：`vars/opnsense/dnat.yml`

该文件当前仅保存审查草案，根键 `opnsense_dnat_rules` 必须是列表。
`manage-dnat.yml` 会验证该形状后**故意失败**，不会执行 API 写入、创建、更新或
删除 NAT/firewall 对象；原因是当前 collection 没有稳定的专用端口转发模块。
不得将示例当作已实现自动化，若需要 DNAT 必须另行设计、审查和实施。

## 2.4 操作流程

先在仓库根目录运行离线 schema 验证：

```bash
make opnsense-validate
```

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
```

一次只变更一种资源类别，并在每次变更后使用 readonly/export 复核。尤其不得
把 Gateway API 用于默认路由接管，也不得将未知的 export 原样作为期望状态。
同一规则集不得无迁移计划地混用手工与 Ansible 所有权；alias 类型变更也不得
由自动 delete/recreate 猜测完成，必须以明确变更单处理。

四个 managed playbook 默认仅在配置发生变化后激活固定资源 target，普通 no-op
不 reload；`--check` 始终不激活。模块内自动 reload 已显式关闭。若 CRUD 批次失败，
之前的项目可能已保存，但本次不会继续 reload，也不自动回滚。若最后 reload 失败，
输出明确区分保存与激活；检查设备后，可用同一 playbook、输入和目标重试，并附加
`-e '{"opnsense_force_reload": true}'`。此选项允许配置已无差异时再次激活。
必须使用 JSON/YAML boolean；`-e opnsense_force_reload=true` 的字符串形式会被拒绝。

Gateway 数值边界与当前固定 Collection 一致：priority 为 0–255，weight 为 1–5，
latency/interval/time_period 为 1–9999，loss_low/high 为 1–99，data_length 为 0–9999。
loss_interval 仅声明整数；工作流不增加 Collection 未声明的范围。整个期望批次在
凭据访问和写入前校验。deny rule 的管理接口保护会同时考虑 destination_net 与
destination_invert；排除自身接口的反选与包含自身接口不是同一种规则。

不要把 `manage-dnat.yml` 加入变更链：它的预期结果是校验输入后失败，以防把
未实现的 DNAT 误认为已被管理。

## 2.5 验收与停止

验收至少包括：API 连通、目标对象身份与顺序正确、管理路径保持可达、所需的
PVE/VM/Registry/DNS 路径经过实际测试，以及未出现未解释的规则阴影或网关
监控告警。API 调用返回成功不等于数据面一定可用。

若管理通道、核心 DNS/路由、既有关键服务或回退路径异常，立即停止后续 PVE/
VM/K3s 变更，保留 export 和变更记录，通过本地控制台恢复。不要批量删除
规则、临时设为默认网关或以未审查的 raw API 请求绕过本工作流。
