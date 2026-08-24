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

`ansible/requirements.yml` 精确锁定 `oxlorg.opnsense` 26.1.11。该版本将 API 有时缺失的
`fargw` 字段作为 `far_gw` 可选字段处理；不要 patch 本机安装的 collection 文件。若升级 collection，先在
隔离环境运行本 playbook 的 syntax check，再确认该兼容性仍然存在。

## `manage-filter-rules.yml`

从手写 YAML 文件增量管理 OPNsense API-backed new firewall filter rules / Rules `[new]`。

输入文件：

```text
vars/opnsense/filter-rules.yml
```

用途：

- 创建、更新或删除 `filter-rules.yml` 中显式列出的 new filter rules。
- 通过 `oxlorg.opnsense.rule_multi` 调用 OPNsense new filter rule API。
- 每个 managed rule 使用 `scope` 和 `slug` 作为不可变 identity parts；playbook 会生成 OPNsense
  `description`：`iaas:opnsense:filter:<scope>:<slug>`。
- 不要在 `opnsense_filter_rules` 中直接声明 `description`；直接声明会在写入前失败。
- OPNsense 侧仍使用生成的 `description` 作为不可变 machine identity，并通过
  `match_fields: ['description']` 匹配既有 rule。例如 `scope: lan` 和 `slug: allow-dns-to-hole` 会生成
  `iaas:opnsense:filter:lan:allow-dns-to-hole`。
- `sequence` 控制规则顺序，但不是 rule identity；修改 `sequence` 应视为同一个 rule 的排序更新。
- `source_net` 和 `destination_net` 可以写字符串或 YAML list；list 会在调用 `rule_multi` 前转换为逗号分隔字符串。
- `source_port` 和 `destination_port` 可省略，省略时表示任意端口；需要限制端口时可写字符串或 YAML list。
  list 会在调用 `rule_multi` 前转换为逗号分隔字符串，例如 `["53", 21115-21117, HOLE_PORTS]`。
- `source_invert` 和 `destination_invert` 可省略，省略时默认为 `false`；只有需要反向匹配时声明为 `true`。
- 建议 sequence blocks：`1-99` essential rules，`100-199` routing-policy rules，`200-499` special rules，
  `900+` broad default allow rules。
- 仅在声明的 filter rule 创建、更新或删除成功后 reload `rule` target 一次。

安全边界：

- 这是写入型 playbook；首次运行前先执行 `snapshot.yml`。
- API 凭据只通过 `OPNSENSE_API_KEY` 和 `OPNSENSE_API_SECRET` 环境变量注入，不写入仓库。
- `vars/opnsense/filter-rules.yml` 是手写 desired state，不由 `download_rules.csv` 或
  `exports/opnsense/` 下的导出文件生成。
- 删除必须通过在 `opnsense_filter_rules` 中显式声明 `state: absent` 完成；未列出的 rules 保持不变。
- 此 playbook 只管理 API-backed new filter rules；不管理 legacy firewall rules。
- 此 workflow 不使用 `setRule/{uuid}` 创建 caller-supplied UUID identity；future UUID identity 是后续单独能力。
- 此 playbook 不管理 NAT、DNAT / port-forward、static routes、gateway groups、interfaces 或 VLANs。

命令：

```bash
op run --env-file ../.env.opnsense.tpl -- uv run ansible-playbook playbooks/opnsense/manage-filter-rules.yml
```

语法检查：

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml
```

Lint：

```bash
uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml
uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml
```

## `manage-dnat.yml`

DNAT / port-forward 管理占位 playbook。

输入文件：

```text
vars/opnsense/dnat.yml
```

用途：

- 为未来 hand-written DNAT desired state 保留与 aliases、VIPs、gateways 类似的位置。
- 当前只加载并校验 `opnsense_dnat_rules` 是 sequence。
- 随后明确失败并提示 DNAT 管理尚未实现。
- 不调用 OPNsense API，不创建、更新或删除任何 NAT / firewall 对象。

原因：

- 当前仓库使用的 `oxlorg.opnsense` collection 暂无稳定的 dedicated Destination NAT / port-forward module。
- 不在此占位 workflow 中使用 raw API workaround；如需 raw API 或未来 native module 支持，应单独设计和评审。

命令：

```bash
uv run ansible-playbook playbooks/opnsense/manage-dnat.yml
```

预期结果：playbook 在读取 `vars/opnsense/dnat.yml` 后失败，并输出 DNAT 管理未实现的提示。

语法检查：

```bash
uv run ansible-playbook --syntax-check playbooks/opnsense/manage-dnat.yml
```

Lint：

```bash
uv run yamllint vars/opnsense/dnat.yml playbooks/opnsense/manage-dnat.yml
uv run ansible-lint playbooks/opnsense/manage-dnat.yml
```

## 当前安全边界

这些 playbook 当前不管理：

- ISC DHCP
- DHCPv6 / prefix delegation
- interfaces / VLANs
- legacy firewall rules
- NAT / DNAT / port-forward
- static routes
- gateway groups
- WAN / PPPoE
- CARP / Proxy ARP / Other VIP modes
