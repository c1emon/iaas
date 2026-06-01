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

## `manage-aliases.yml`

从手写 YAML 文件增量管理 OPNsense firewall aliases。

输入文件：

```text
vars/opnsense/aliases.yml
```

用途：

- 创建或更新 `aliases.yml` 中列出的 aliases。
- 对未列出的 aliases 不执行删除、禁用或 purge。
- 仅在 alias 创建或更新成功后 reload alias target 一次。

安全边界：

- 这是写入型 playbook；首次运行前先执行 `snapshot.yml`。
- API 凭据只通过 `OPNSENSE_API_KEY` 和 `OPNSENSE_API_SECRET` 环境变量注入，不写入仓库。
- `exports/opnsense/firewall-aliases.json` 是 live state 观察结果，不是此 playbook 的直接输入。
- alias `type` 变更不会自动通过删除/重建迁移；需要操作者显式处理。
- 此 playbook 不管理 firewall rules、NAT、interfaces、DHCP 或 Unbound。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-aliases.yml
```

语法检查：

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-aliases.yml
```

Lint：

```bash
uv run yamllint vars/opnsense/aliases.yml playbooks/opnsense/manage-aliases.yml
uv run ansible-lint playbooks/opnsense/manage-aliases.yml
```

## `manage-vips.yml`

从手写 YAML 文件增量管理 OPNsense IP Alias Virtual IPs。

输入文件：

```text
vars/opnsense/vips.yml
```

用途：

- 创建、更新或删除 `vips.yml` 中显式列出的 IP Alias VIPs。
- 对未列出的 VIPs 不执行删除、禁用或 purge。
- 强制使用 `mode: ipalias`，不从输入文件接受 CARP、Proxy ARP 或 Other VIP modes。
- `interface` 必须写 OPNsense interface identifier / network port value，例如 `lan`、`wan`、`opt1`；
  不写 UI display name 或自定义名称，例如 `LAN`、`MGMT`。
- 仅在声明的 VIP 创建、更新或删除成功后 reload `interface_vip` target 一次。

安全边界：

- 这是写入型 playbook；首次运行前先执行 `snapshot.yml`。
- API 凭据只通过 `OPNSENSE_API_KEY` 和 `OPNSENSE_API_SECRET` 环境变量注入，不写入仓库。
- `vars/opnsense/vips.yml` 是手写 desired state，不由 `exports/opnsense/` 下的导出文件生成。
- 删除必须通过在 `opnsense_vips` 中显式声明 `state: absent` 完成；未列出的 VIPs 保持不变。
- 此 playbook 不管理 CARP、Proxy ARP、Other VIP modes、DNAT、NAT、firewall rules、interfaces 或 VLANs。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-vips.yml
```

语法检查：

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-vips.yml
```

Lint：

```bash
uv run yamllint vars/opnsense/vips.yml playbooks/opnsense/manage-vips.yml
uv run ansible-lint playbooks/opnsense/manage-vips.yml
```

## `manage-gateways.yml`

从手写 YAML 文件增量管理用于 policy-based routing 的 OPNsense gateway objects。

输入文件：

```text
vars/opnsense/gateways.yml
```

用途：

- 创建、更新或删除 `gateways.yml` 中显式列出的 PBR gateway objects。
- 对未列出的 gateways 不执行删除、禁用、purge 或批量 reconciliation。
- 强制每个声明的 gateway 使用 `default_gw: false`，避免此 workflow 接管 default route。
- `interface` 必须写 OPNsense interface identifier / network port value，例如 `lan`、`wan`、`opt1`；
  不写 UI display name 或自定义名称，例如 `LAN`、`MGMT`、`DMZ`。
- FakeIP PBR 中 aliases 和 VIPs 是先决条件；gateway 提供后续 firewall PBR rule 可引用的
  `GW_PROXY` next-hop。PBR firewall rules 仍是单独的未来能力。
- 仅在声明的 gateway 创建、更新或删除成功后 reload `gateway` target 一次。

安全边界：

- 这是写入型 playbook；首次运行前先执行 `snapshot.yml`。
- API 凭据只通过 `OPNSENSE_API_KEY` 和 `OPNSENSE_API_SECRET` 环境变量注入，不写入仓库。
- `vars/opnsense/gateways.yml` 是手写 desired state，不由 `exports/opnsense/` 下的导出文件生成。
- 删除必须通过在 `opnsense_gateways` 中显式声明 `state: absent` 完成；未列出的 gateways 保持不变。
- 此 playbook 不管理 firewall rules、DNAT、outbound NAT、static routes、gateway groups、interfaces 或 VLANs。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-gateways.yml
```

语法检查：

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-gateways.yml
```

Lint：

```bash
uv run yamllint vars/opnsense/gateways.yml playbooks/opnsense/manage-gateways.yml
uv run ansible-lint playbooks/opnsense/manage-gateways.yml
```

已知问题：`oxlorg.opnsense.gateway` 在读取现有 OPNsense 动态/虚拟 gateway 时，可能因为 API
返回缺少 `fargw` 字段而失败，例如：

```text
Failed to translate API entry to Ansible entry!
Failed field: 'far_gw'
```

这是 collection 的字段转换兼容性问题，不是 `gateways.yml` 输入错误。当前本机临时修复是 patch 已安装的
collection 文件：

```text
~/.ansible/collections/ansible_collections/oxlorg/opnsense/plugins/module_utils/helper/main.py
```

在 `simplify_translate()` 的 typed field 循环里，对缺失字段跳过：

```python
if f not in simple:
    continue
```

重新安装或升级 `oxlorg.opnsense` collection 后，这个本地 patch 可能会被覆盖；届时需要重新 patch，或等待
upstream 修复。已知有类似 upstream issue 模式，例如缺失 API 字段导致 translation failure，但未找到专门针对
`gateway` + `far_gw` 的 issue。

## 当前安全边界

这些 playbook 当前不管理：

- ISC DHCP
- DHCPv6 / prefix delegation
- interfaces / VLANs
- firewall rules
- NAT
- static routes
- gateway groups
- WAN / PPPoE
- CARP / Proxy ARP / Other VIP modes
