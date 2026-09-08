# 4. VM Bootstrap：来宾基线、APT 源与出站策略

本章在 PVE 已创建、cloud-init 已完成且 guest verification 可用后执行。它负责
Debian 来宾内的基线策略与可选软件包出站策略；不修改 PVE VM 生命周期、NIC、
路由、DNS、OPNsense、交换机或 K3s/containerd registry 文件。

## 4.1 输入与责任边界

| 输入 | 来源 | 用途 |
| --- | --- | --- |
| guest SSH/网络事实 | `$GENERATED_DIR/ansible/pve.yml` | `ops` 用户、sudo、`pve_nics`、目标 host。 |
| 共同基线 | `automation/ansible/roles/vm_baseline/` | 包、服务、hostname、reboot 标记、网络事实核验。 |
| 可选 egress policy | 仓库外或已审查的环境 vars 文件 | APT source、keyring、CA、APT/Shell/Git proxy。 |
| egress runtime JSON | 仓库外受保护文件 | 仅在 policy 引用外部秘密时提供。 |

Packer 的 `apt_mirror`/`apt_security_mirror` 是**模板构建期**输入；egress policy
是**已创建来宾的持续基线**。K3s 的 artifact/registry/service proxy 又是独立的
K3s/containerd 策略。三者不能混写到同一 YAML。

## 4.2 `vm_baseline` 参数

角色默认值位于 `automation/ansible/roles/vm_baseline/defaults/main.yml`：

| 变量 | 含义 | 默认/约束 |
| --- | --- | --- |
| `vm_baseline_packages` | 要安装的基线包。 | 默认空列表；包策略必须明确。 |
| `vm_baseline_time_sync_packages` | 时间同步相关包。 | 默认空列表。 |
| `vm_baseline_update_cache` | 安装前是否更新 APT cache。 | 默认 `false`；不可隐式引入 `apt update`。 |
| `vm_baseline_cache_valid_time` | APT cache 有效期秒数。 | 默认 `3600`；仅在显式更新策略下相关。 |
| `vm_baseline_services` | 受角色管理的服务。 | 默认空列表。 |
| `vm_baseline_hostname_mode` | hostname 处理模式。 | 默认 `converge`；要与 inventory host 名一致。 |
| `vm_baseline_report_reboot_required` | 是否报告 reboot 标记。 | 默认 `true`；报告不是自动重启。 |
| `vm_baseline_network_validation_mode` | 网络事实处理。 | 默认 `report`；可为 `assert` 或 `disabled`。 |
| `vm_baseline_network_gateway` / `dns` | 预期连接 NIC 网关/DNS。 | 由 bootstrap playbook 从唯一 `ansible_connection` NIC 派生。 |
| `vm_baseline_egress_policy` | 可选 egress 根对象。 | 空对象表示不管理该策略。 |
| `vm_baseline_egress_runtime_secret_file` | 受保护 secret 文件路径。 | 只有 policy 需要时才提供。 |

`report` 仅报告预期与实际 IP、网关、DNS；`assert` 会因不一致失败；`disabled`
跳过该比较。无论哪种模式，角色都不配置网卡或路由，只读取实际 facts。

## 4.3 egress policy 文件与字段

Bootstrap playbook 只接受根键 `vm_baseline_egress_policy` 的 YAML 文件。其必须
与 PVE inventory 分离，且不得含密码、token、私钥或证书正文。示例为结构示意，
引用和 checksum 必须由实际环境替换：

```yaml
vm_baseline_egress_policy:
  state: present
  keyrings:
    - id: example-repo
      kind: role_managed
      artifact: /secure/controller/example.gpg
      sha256: <64-hex-sha256>
  custom_cas: []
  sources:
    - id: example-repo
      uri: https://packages.example.invalid
      suites: [stable]
      components: [main]
      keyring: example-repo
  proxy:
    mode: direct
  extra_bypass: []
  exclusive_sources: false
  shell_proxy:
    enabled: false
  git_proxy:
    enabled: false
```

| 字段 | 含义 | 约束/效果 |
| --- | --- | --- |
| `state` | `present` 或 `absent`。 | `present` 需要至少一个 source；`absent` 只清理确定的角色托管路径。 |
| `keyrings[]` | APT 签名 keyring。 | `id` 唯一；`kind` 为 `role_managed` 或现有路径策略；artifact 与 `sha256` 必须成对。 |
| `custom_cas[]` | 来宾信任的自定义 CA。 | `id` 唯一，artifact 与 SHA-256 受校验；不把 CA 正文写入 policy。 |
| `sources[]` | deb822 APT source。 | `id` 唯一，`uri` 为 HTTP(S) endpoint，`suites`/`components` 非空，`keyring` 必须引用声明的 keyring。 |
| `proxy.mode` | `direct` 或 `proxy`。 | `proxy` 时需要 endpoint；可选 `secret_ref` 必须是 `op://` 外部引用。 |
| `proxy.endpoint` | APT HTTP(S) proxy。 | 非秘密 endpoint；认证值在受保护运行时文件。 |
| `extra_bypass` | 除连接 NIC 相关地址外的 `no_proxy` 项。 | 仅显式、有界的 host/IP/CIDR。 |
| `exclusive_sources` | 是否拒绝未受管理的 source 冲突。 | 默认 `false`；启用前先审查全部已有 source。 |
| `shell_proxy` / `git_proxy` | `{enabled, endpoint}`。 | 默认关闭；endpoint 不含认证信息；不会为此自动安装 Git。 |

`present` 可管理 role-owned deb822 source、签名 keyring、CA、APT proxy/auth、
可选 shell/Git proxy。它的路径是确定的：例如 APT proxy 为
`/etc/apt/apt.conf.d/80-vm-baseline-proxy`，shell proxy 为
`/etc/profile.d/vm-baseline-proxy.sh`，Git proxy 为
`/etc/gitconfig.d/vm-baseline-proxy.conf`。`absent` 不删除未知 APT source 或
人工文件。回退方式是保存上一份已审查 policy 并以相同 scope 重跑，而不是省略
policy 或删除 generated file。

完整的 role-owned 路径族为：

```text
/etc/apt/keyrings/vm-baseline-<id>.gpg
/etc/apt/sources.list.d/vm-baseline-<id>.sources
/usr/local/share/ca-certificates/vm-baseline-<id>.crt
/etc/apt/apt.conf.d/80-vm-baseline-proxy
/etc/apt/auth.conf.d/80-vm-baseline-auth.conf
/etc/profile.d/vm-baseline-proxy.sh
/etc/gitconfig.d/vm-baseline-proxy.conf
```

`<id>` 是小写 policy identity，不是任意路径片段。有效 bypass 集由 generated
inventory 的 `pve_nics`（包括连接 NIC 的地址/子网）和 `extra_bypass` 共同导出；
不要把 VM IP/CIDR 复制进 policy。APT 使用仓库主机的 `DIRECT` 条目，shell/Git
只接收各自支持的形式。带认证的 proxy 只能通过受保护 runtime 注入，绝不能写入
shell profile、全局 Git 配置、inventory、生成物、facts、diff 或普通控制端临时文件。

## 4.4 执行顺序

以下命令继承准备章节中的 `ENVIRONMENT_DIR`、`OUTPUT_DIR` 和 `GENERATED_DIR`。
新终端须先按该章节重新设置目录，不会自动选择任何环境。

先运行语法检查。若未选 egress policy，可省略两个 egress 变量：

```bash
make pve-bootstrap-guests-syntax
```

对明确单台/明确组 VM 引入 policy 时，先选择 policy 文件和受保护 runtime JSON：

```bash
make pve-bootstrap-guests-syntax \
  ANSIBLE_LIMIT=<generated-vm-host> \
  VM_BASELINE_EGRESS_POLICY=/safe/path/reviewed-egress-policy.yml

make pve-bootstrap-guests \
  ANSIBLE_LIMIT=<generated-vm-host> \
  VM_BASELINE_EGRESS_POLICY=/safe/path/reviewed-egress-policy.yml \
  VM_BASELINE_EGRESS_RUNTIME_SECRETS=/safe/path/protected-runtime.json
```

未指定 `ANSIBLE_LIMIT` 时，入口的默认范围是 `pve_vms`；不要在首次应用新策略时
无意扩展到所有主机。选定 policy 文件不可读时，playbook 会在联系 guest 前失败。

完成后运行：

```bash
make pve-verify-guests
```

检查 hostname、静态 IP、gateway、DNS、qemu-guest-agent、SSH/sudo、root SSH
边界及预期软件包/服务结果。若该 VM 将成为 K3s 节点，还需满足
[K3s preflight](05-k3s.md)；guest baseline 成功不等于 cgroups、端口、时间、
artifact、registry 或 K3s API 已准备好。

## 4.5 停止与交接

出现 source/keyring/CA checksum 不匹配、APT source 冲突、代理秘密缺失、网络
事实异常、无法解释的 package 失败或 guest SSH 不通时，停止并先恢复该 VM 的
可访问性。不要以全局 shell proxy、手工改 `/etc/rancher/k3s/`、修改 PVE DHCP/
路由或跳过 checksum 解决。

交给 K3s 的 VM 必须具有：唯一的 Ansible 连接 NIC、明确 K3s node-network role
的 NIC、正确的默认路由与 DNS、可用的 `ops` sudo、足够磁盘与时间同步，以及
经审查的 artifact/Registry 网络路径。
