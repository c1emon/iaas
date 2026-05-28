# OPNsense Playbooks

这些 playbook 通过 HTTPS API 管理或检查 OPNsense。API 凭据在运行时注入，不写入仓库。

除非特别说明，以下命令都从 `ansible/` 目录执行。

## `readonly.yml`

只读 API 冒烟测试。

用途：

- 验证 1Password / 环境变量中的凭据注入是否正常。
- 验证 Ansible 是否可以访问 OPNsense API。
- 查询 firewall aliases，不修改 OPNsense。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/readonly.yml
```

## `snapshot.yml`

在未来执行写入型变更前，创建 OPNsense 配置快照。

用途：

- 在 OPNsense 配置历史中创建一个回滚点。
- 在运行写入型 playbook 前执行。

注意：这不是 VM 快照，也不是磁盘快照。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/snapshot.yml
```

## `export.yml`

只读导出部分 OPNsense 配置和观测事实。

用途：

- 导出第一阶段可考虑接管的配置：
  - firewall aliases
  - Unbound host overrides
  - Unbound forwarding entries
- 导出仅用于观察的 DHCP 事实：
  - DHCPv4 leases
  - DHCPv6 leases
  - DHCPv6 prefix leases

输出目录：

```text
exports/opnsense/
```

`exports/` 已被 Git 忽略，因为原始导出可能包含网络拓扑、主机名、MAC 地址、租约数据和 IPv6 前缀信息。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/export.yml
```

## 当前安全边界

这些 playbook 当前不管理：

- ISC DHCP
- DHCPv6 / prefix delegation
- interfaces / VLANs
- firewall rules
- NAT
- WAN / PPPoE
