# 1. 交换机

本章覆盖 SKS8300/XikeOS 的连接、只读事实收集和受控资源配置。交换机是
OPNsense、PVE、存储和 K3s 多网卡路径的物理/L2 前提，但本仓库不会根据
PVE 或 K3s 配置自动创建 VLAN、端口或 Trunk。

## 1.1 准入与交接

开始前确认：

- 管理网到目标交换机的 SSH 可达，且具备本地/串口恢复路径；
- 已审查需要承载的 VLAN、PVE bridge、OPNsense 接口、TrueNAS 存储 VLAN 和
  K3s 网络角色；
- 本次范围仅包含明确端口和资源；没有把临时排障命令混入声明式配置；
- 先执行只读事实或 plan，再决定是否允许变更。

向 [OPNsense](02-opnsense.md) 交接时，应能说明每个相关 VLAN 的 L2 承载、
上联/下联端口、访问或 trunk 模式及允许 VLAN；不要声称 L2 通而 L3/防火墙也
必然通。

## 1.2 配置文件与参数

| 文件 | 作用 | 可编辑性 |
| --- | --- | --- |
| `$ENVIRONMENT_DIR/ansible/inventory.yml` | `switches` 组、主机名、管理地址、设备型号提示。 | 环境源文件。 |
| `$ENVIRONMENT_DIR/ansible/group_vars/switches.yml` | 连接插件、平台、运行时用户名/密码、端口、超时。 | 环境源文件；凭据只通过环境变量。 |
| `$ENVIRONMENT_DIR/ansible/vars/switches/<inventory_hostname>-vlans.yml` | 所选主机 的声明式资源调用。 | 环境源文件；默认仅 plan。 |
| `$OUTPUT_DIR/runtime/exports/switches/` | 只读事实导出。 | 本地观察产物；不得作为 apply 输入或提交。 |

### 连接变量

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `ansible_connection` | 必须为 `ansible.netcommon.network_cli`。 | 不改为本地 shell 或通用 SSH 命令通道。 |
| `ansible_network_os` | 必须为 `c1emon.xikeos.xikeos`。 | 使用本仓库原生 XikeOS collection。 |
| `ansible_user` | SSH 用户，来自 `SWITCH_SSH_USER`。 | 不写入 YAML。 |
| `ansible_password` | SSH 密码，来自 `SWITCH_SSH_PASSWORD`。 | 不写入 YAML、facts 或日志。 |
| `ansible_port` | SSH 端口，默认环境变量为空时为 `22`。 | 必须非空。 |
| `ansible_command_timeout` | 单命令超时秒数。 | 由调用方声明；根据设备响应设置。 |
| `switch_model_hint` | 操作者阅读用型号提示。 | 不替代真实设备能力探测。 |

### 只读事实选择与导出参数

`readonly-facts.yml` 直接调用 `c1emon.xikeos.xikeos_facts`，不会进入配置模式。
控制端使用 `paramiko` 作为 `network_cli` 的 Python SSH 后端；不得改用旧 Cisco IOS
adapter、Cisco IOS resource/config 模块或通用 `cli_config`。仓库约束原生 collection
版本为 `>=0.2.1,<0.3.0`，需要与 `uv sync` 一起安装；facts/resource 解析依赖（包括
`ttp`、`textfsm`）也必须在控制端可用。

| 变量 | 默认/允许值 | 作用与约束 |
| --- | --- | --- |
| `switch_readonly_gather_subset` | 默认 `[min]`；允许 `all`、`min`、`hardware`、`config` 及对应 `!` 排除项。 | 传给原生 facts 模块；必须非空。 |
| `switch_readonly_gather_network_resources` | 默认 `interfaces`、`vlans`、`l2_interfaces`、`l3_interfaces`、`lag_interfaces`、`static_routes`、`acls`。 | 允许上述资源、`all` 和对应 `!` 排除项；必须非空。 |
| `switch_export_formats` | 默认 `[yaml, json]`。 | 仅控制结构化观察产物格式。 |
| `switch_export_save_raw` | 默认 `false`。 | `true` 才保存原始 CLI 输出；只能用于明确排障，导出视为敏感本地材料。 |
| `switch_export_dir` / `switch_raw_output_dir` | 默认 `exports/switches/<inventory_hostname>/` 及其 `raw-output/` 子目录。 | 本地观察路径，绝不作为 desired-state 输入或提交。 |

计划会显示按资源分组的对象变更（新增、删除、更新及变化字段），不显示命令、描述或地址值。
未变化的计划显示 `changed_objects: 0`。需要原始详情时，显式传入
`-e switch_config_detail_dir=/absolute/private/report-directory`；每台设备写入
`<目录>/<inventory_hostname>/plan.json`，目录权限为 `0700`、文件为 `0600`。
详情可能包含拓扑信息；目录必须位于实现代码和环境手写输入之外。

### `switch_config_resources` 结构

`<inventory_hostname>-vlans.yml` 的根对象为 `switch_config_resources`。允许的资源组为
`vlans`、`base_interfaces`、`lag_interfaces`、`l2_interfaces`、`l3_interfaces`、
`static_routes` 和 `acls`。每个资源组的值均是模块调用列表：

```yaml
switch_config_allowed_states:
  - merged
switch_config_resources:
  vlans:
    - state: merged
      config:
        - vlan_id: 3999
          name: example
  l2_interfaces:
    - state: merged
      config:
        - name: Ethernet1/0/48
          mode: access
          access_vlan: 3999
```

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `switch_config_allowed_states` | 本次允许交给 collection 的 state 白名单。 | 默认只有 `merged`；扩展到 `deleted`/`replaced` 前必须单独评估影响。 |
| 资源组名称 | 对应一个 XikeOS 原生资源模块。 | 未知资源组会被拒绝。 |
| `state` | 该资源调用的 collection state。 | 必须出现在白名单。 |
| `config` | 一组传给原生模块的资源对象。 | 必须是 YAML 列表；具体字段遵循相应 collection 模块。 |
| `vlan_id` / `name` | VLAN 标识与可读名称。 | `vlan_id` 必须与目标网络设计和现有设备事实一致。 |
| `name` / `mode` | 接口名和 access/trunk 模式。 | 对端、端口角色和管理路径必须先确认。 |
| `access_vlan` | access 端口 VLAN。 | 仅适用于审查后的 access 端口。 |
| `trunk_allowed_vlan` | trunk 允许 VLAN 列表。 | 只显式允许所需 VLAN，避免无界 trunk。 |

资源组按下列固定顺序调用原生模块：

| 资源组 | 原生模块 |
| --- | --- |
| `vlans` | `c1emon.xikeos.xikeos_vlans` |
| `base_interfaces` | `c1emon.xikeos.xikeos_interfaces` |
| `lag_interfaces` | `c1emon.xikeos.xikeos_lag_interfaces` |
| `l2_interfaces` | `c1emon.xikeos.xikeos_l2_interfaces` |
| `l3_interfaces` | `c1emon.xikeos.xikeos_l3_interfaces` |
| `static_routes` | `c1emon.xikeos.xikeos_static_routes` |
| `acls` | `c1emon.xikeos.xikeos_acls` |

`config` 是已安装 collection 的原生 schema，不是仓库别名。当前版本中 L3 与
LAG 的 `merged` 调用是加法式的：省略地址或成员不会删除它们。STP、ERPS、EAPS、
QinQ、mirror、port isolation、flex monitor link 和 OSPF v2 等仅有 rendered-only
能力的资源不接受本工作流；`xikeos_config` 也不是日常路径。若需要这些能力，
必须另行设计受控工作流，不能绕过本章直接发 CLI。

仓库拒绝旧的 `switch_config_intent`、任意 `switch_config_commands` 和原始 CLI
命令列表。collection 的 check-mode 输出若包含 reload、erase、factory reset 等
危险命令模式也会被拒绝。

## 1.3 操作流程

在 `automation/ansible/` 目录执行以下命令。先按准备章节安装依赖并设置绝对目录。以下使用调用方 `op run` 模板示例；
传统 Secret 已注入相同环境变量时，直接执行其后的 `uv run` 命令。
调用方 group vars 负责将环境变量映射为相应 Ansible 连接变量。

```bash
export SWITCH_HOST="your-switch-inventory-host"
cd automation/ansible

# 在线只读：先验证 SSH/network_cli 基本链路。
op run --env-file "$SWITCH_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/switches/network-cli-smoke.yml -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$SWITCH_HOST"

# 在线只读：收集原生事实并生成本地观察产物。
op run --env-file "$SWITCH_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/switches/readonly-facts.yml -e "switch_export_dir=$OUTPUT_DIR/runtime/exports/switches/$SWITCH_HOST" -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$SWITCH_HOST"

# 在线但默认不变更：由原生模块以 check mode 预览声明式资源。
op run --env-file "$SWITCH_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/switches/config-plan.yml -e "ansible_project_dir=$ENVIRONMENT_DIR" -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$SWITCH_HOST" \
  --check -e switch_config_apply=false
```

事实收集支持 `switch_export_formats`（`yaml`、`json`）和
`switch_export_save_raw`。默认不保存原始输出；只有明确排障范围时才启用，且
应将导出视为可能含敏感拓扑数据的本地观察文件。

只有审查过 plan、记录恢复路径并确认不会切断控制通道后，才可显式执行变更：

```bash
op run --env-file "$SWITCH_ENV_TEMPLATE" -- \
  uv run ansible-playbook playbooks/switches/config-plan.yml -e "ansible_project_dir=$ENVIRONMENT_DIR" -i "$ENVIRONMENT_DIR/ansible/inventory.yml" --limit "$SWITCH_HOST" \
  -e switch_config_apply=true
```

这不是“全部配置同步”。它只对 `switch_config_resources` 中的明确调用执行允许的
state，且不会自动创建 PVE bridge、OPNsense 接口、路由策略或 K3s 网络。

## 1.4 验收与停止

成功证据应包括：目标 SSH 连通、只读事实中端口/VLAN 状态符合审查意图、plan
没有危险命令、变更后管理路径仍可达，以及下游所需 L2 链路已明确验证。不能用
“playbook 无报错”替代端到端的 VLAN/链路验证。

若控制通道、上联、管理 VLAN、目标端口状态或 collection 输出异常，停止后续
OPNsense/PVE 操作，使用预先确认的控制台路径恢复。不要用未审查的原始 CLI、
批量删除 state 或工厂重置来补救。
