# SW_CORE

## SKS8300-12X 交换机 CLI 纳管结论

- 设备可通过 Telnet 登录，登录后提示符为 `Switch#`。
- `show version` 可用，设备信息显示为 `SKS8300-12X`，软件版本 `V300SP10240912`。
- CLI 属于 **Cisco-like 自有 CLI**：支持类似 Cisco 的 `show` 命令和特权模式提示符，但不是标准 Cisco IOS。
- 标准 Cisco IOS 配置入口 `configure terminal` 不可用，会返回 `% Invalid input detected`。
- 正确配置入口为：

```text
config
```

- 进入配置模式后提示符为：

```text
Switch(config)#
```

### 纳管建议

- 可以作为非官方支持设备纳入管理。
- 只读采集/备份可优先使用通用 CLI 命令，例如 `show version`、`show running-config`、`show vlan`、`show interfaces`。
- 不建议直接使用标准 Cisco IOS 配置模块，例如 `cisco.ios.ios_config`，因为配置入口不兼容。
- 推荐使用通用 CLI/Telnet 自动化方式，例如 Ansible `ansible.netcommon.cli_command` 或自定义平台 profile。
- 建议平台 profile 关键参数：

```yaml
platform: sks8300
prompt: 'Switch[#>]|Switch\(config\)#'
config_mode: config
exit_config_mode: exit
save_config: write
disable_paging: terminal length 0
```

- 后续仍需验证分页关闭、配置保存和常用状态命令是否兼容，例如：

```text
terminal length 0
show running-config
write
show startup-config
```

## VLAN 相关只读探索结果

### 可用命令

- `terminal length 0` 可用，可用于关闭分页。
- `show vlan` 可用，可显示 VLAN 名称、类型和端口成员。
- `show vlan brief` 可用，可显示已存在 VLAN 列表。
- `show interface` 可用，注意该设备使用单数 `interface`，不是 `interfaces`。
- `show mac-address-table` 可用，注意命令中为 `mac-address-table`，不是 Cisco 常见的 `mac address-table`。
- `show running-config` 可用，可用于提取 VLAN 和端口配置。
- `show running-config | include vlan` 可用，可用于快速筛选 VLAN 相关配置行。

### 不兼容/不可用命令

- `show interfaces switchport` 不可用。
- `show interfaces status` 不可用。
- `show interfaces ?` 不可用；该设备使用 `show interface ?`。
- `show mac address-table` 为歧义命令；应使用 `show mac-address-table`。

### 当前 VLAN

```text
1    default
10   dev
21   isp
33   storage
40   hole
50   prod
99   lan
```

### 端口 VLAN 配置摘要

```text
Ethernet1/0/1   默认 VLAN 1，未显式配置
Ethernet1/0/2   hybrid，tag: 1;21;99
Ethernet1/0/3   hybrid，tag: 1;10;21;33;40;50;99
Ethernet1/0/4   hybrid，tag: 1;10;21;40;50;99，media-type fiber-10g
Ethernet1/0/5   trunk，allowed vlan 10;50
Ethernet1/0/6   trunk，allowed vlan 10;50
Ethernet1/0/7   trunk，allowed vlan 10;50
Ethernet1/0/8   access vlan 50
Ethernet1/0/9   access vlan 33
Ethernet1/0/10  access vlan 33
Ethernet1/0/11  access vlan 33
Ethernet1/0/12  access vlan 33
```

### 管理 SVI

```text
interface Vlan1
 ip address 10.1.0.20 255.255.255.0
```

### 自动化注意事项

- 备份/采集 VLAN 配置建议优先使用 `show running-config` 和 `show vlan`。
- 端口状态和 PVID 可通过 `show interface` 解析。
- MAC 地址表采集使用 `show mac-address-table`。
- `show running-config` 会输出本地用户配置；采集结果需要脱敏后再保存或提交。
