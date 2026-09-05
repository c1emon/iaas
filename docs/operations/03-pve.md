# 3. PVE：模板、虚拟机与主机维护

本章从已验证的交换机和 OPNsense 路径开始，创建可供 VM bootstrap 与 K3s 使用
的 Debian 来宾。PVE 所有权仅限模板、VM 生命周期、磁盘、NIC 附着和 cloud-init
介质；它不创建物理 bridge/VLAN、OPNsense 规则、DNS 记录或 K3s 集群。

## 3.1 准入

在执行 PVE 计划或变更前确认：

- [交换机](01-switch.md) 已确认目标 bridge 的 L2 承载；[OPNsense](02-opnsense.md)
  已确认管理、软件源、Registry 和必要存储路径；
- 每个目标 PVE 节点有可用 API/SSH 运行时凭据及带外/本地控制台；
- 目标存储、bridge、模板、VMID、MAC、IP 和 PCI mapping 已在源 YAML 中声明且
  没有冲突；
- 已运行离线生成/校验，并保存 PVE state 备份策略和本次变更记录；
- 对 long-lived VM、passthrough VM 和可能替换模板的操作已有恢复决策。

`make pve-preflight` 是在线 apply-readiness 检查，不是“PVE 正常”的唯一证明；
`make pve-health` 是当前声明的集群/节点健康检查。二者都不迁移、停止或销毁 VM。

## 3.2 PVE 源配置总览

| 文件 | 所有权 | 产物/用途 |
| --- | --- | --- |
| `environments/astra/inventory/pve-cluster.yml` | PVE 集群共享事实、模板、网络、存储角色、VM 默认值和 PCI mappings。 | 归一化模型、OpenTofu input、Ansible inventory、Packer env、PVE VM 文档。 |
| `environments/astra/inventory/vms.yml` | 单个 VM 的生命周期、NIC、资源、启动、HA 与 passthrough。 | 同上。 |
| `environments/astra/generated/opentofu/pve.tfvars.json` | 生成的 OpenTofu 输入。 | 只审查，不手改。 |
| `environments/astra/generated/ansible/pve.yml` | 生成的 VM SSH/网络事实。 | VM bootstrap、guest verify、K3s inventory 输入。 |
| `environments/astra/generated/packer/debian-13.env` | 非敏感模板构建参数。 | Packer helper 输入。 |
| `environments/astra/generated/docs/pve-vms.md` | VM 声明的可读表格。 | 审查参考，不是源配置。 |
| `environments/astra/runtime/.env.pve-opentofu.tpl` | PVE API、SSH 和 cloud-init 用户材料的运行时变量名。 | 仅通过 1Password 注入。 |

先运行：

```bash
make pve-check
make pve-ansible-syntax
make pve-bootstrap-guests-syntax
```

`pve-check` 只校验源与已提交生成物是否一致；不检查实际 PVE bridge、存储、模板
或来宾可达性。

## 3.3 PVE 节点自动化账户与模板 helper

在首次构建模板前，PVE 节点需要 `pve-ops` 自动化账户和 root-owned template
wrapper。使用一个已有的、受控的 PVE 管理账户与 runtime 提供的 SSH 公钥执行：

```bash
cd automation/ansible
PVE_SSH_AUTOMATION_PUBLIC_KEY="$(op read op://Astra/pve-ssh-automation-user/public_key)" \
  uv run ansible-playbook -i '<pve-node>,' -u <existing-admin-login> --become \
  playbooks/pve/bootstrap-pve-ops.yml \
  -e pve_bootstrap_authorized_key="$PVE_SSH_AUTOMATION_PUBLIC_KEY"
```

该 playbook 创建并锁定 `pve-ops` 密码、安装 SSH 公钥、验证 sudoers。临时的
多命令 preflight sudo 白名单只能在明确窗口内使用，验证后必须缩回到 wrapper-only
规则。它不更改全局 SSHD 策略。

在每个 PVE build node 安装并检查 wrapper：

```bash
sudo install -m 750 -o root -g root \
  automation/pve-node/bin/astra-pve-template-build \
  /usr/local/sbin/astra-pve-template-build
# 先复制 sudoers 文件到临时路径，以 visudo 校验后再以 root:root / 0440 安装。
sudo visudo -cf <temporary-sudoers-file>
```

PVE 节点需具备 `curl`、`shasum`、`cp`、`virt-customize`、`virt-sysprep`、`qm`
和 `flock`；安装 `libguestfs-tools` 可提供两个 `virt-*` 工具。wrapper 与 sudoers
必须保持 root-owned，`pve-ops` 仅能无密码执行
`/usr/local/sbin/astra-pve-template-build`。可用下列只读 smoke 验证安装：

```bash
ssh <existing-admin-login>@<pve-node> \
  'sudo -n visudo -cf /etc/sudoers.d/astra-pve-template-build'
ssh pve-ops@<pve-node> 'sudo -n /usr/local/sbin/astra-pve-template-build --help'
```

## 3.4 `pve-cluster.yml` 参数

### 集群、VMID 和存储

| 路径 | 含义 | 约束/影响 |
| --- | --- | --- |
| `schema_version` | 当前 schema 版本。 | 必须为 `1`。 |
| `cluster.name` | PVE 环境标识。 | 用于生成的描述文本。 |
| `cluster.default_template` | 未覆盖时采用的 template key。 | 必须引用 `templates` 中的条目。 |
| `reserved_vm_id_ranges.templates` | 模板 VMID 闭区间。 | 与其他区间不重叠。 |
| `reserved_vm_id_ranges.long_lived` | 长期 VMID 闭区间。 | long-lived VM 只能落入此范围。 |
| `reserved_vm_id_ranges.ephemeral_lab` | 实验/可重建 VMID 闭区间。 | ephemeral VM 只能落入此范围。 |
| `storage_roles.<role>.datastore` | PVE 实际 datastore 名称。 | role 是可移植符号；存储必须承载声明的 content。 |
| `storage_roles.<role>.purpose` | 给操作者的用途说明。 | 不替代 PVE 真实能力检查。 |
| `storage_roles.<role>.content` | `disk`、`iso`、`import`、`snippets` 等内容类型。 | 生成器会校验 template/cloud-init 的 role 是否具备所需内容。 |

### 网络与 PVE 节点

| 路径 | 含义 | 约束/影响 |
| --- | --- | --- |
| `networks.<name>.bridge` | 既有 PVE host bridge。 | OpenTofu 只附着 NIC；不会创建或修改该 bridge。 |
| `networks.<name>.cidr` | 网络的规范 CIDR。 | VM 静态 IP、网关和 DNS 必须归属并保持一致。 |
| `gateway` / `dns` | 该逻辑网络默认网关与解析器。 | 非默认路由网络可为 `null`；不自动管理 OPNsense/DNS。 |
| `attach_vms` | 是否允许普通 VM NIC 附着。 | `false` 的基础设施网络默认拒绝 VM 引用。 |
| `nodes.<node>.mgmt_ip` | PVE 管理地址。 | 用于在线检查/操作记录，非 VM 地址。 |
| `nodes.<node>.storage_ip` | PVE 存储网络地址。 | 不自动开放存储路径。 |
| `nodes.<node>.ssh_host` | 控制机 SSH alias/地址。 | 若 alias 无法解析，显式使用已确认的管理 IP；不要猜测主机名。 |

### 模板构建与 cloud-init

`cluster.automation.template_build` 是 Debian genericcloud 模板材料：
`template_key`、`image_url`、`image_sha512`、`image_url_prefix`、
`import_storage_role`、`disk_storage_role`、`build_domain`、`apt_mirror`、
`apt_security_mirror`、`timezone`、`locale`、`ciuser`、`nameserver` 与
`build_bridge`。URL 必须在允许前缀内，SHA-512 是镜像身份，不得用“最新”替代；
APT 镜像只用于模板构建，不能替代 [VM bootstrap](04-vm-bootstrap.md) 的来宾
软件源策略。

### 生成的 Packer 环境与构建开关

`make generate` 从上述 `template_build` 生成
`environments/astra/generated/packer/debian-13.env`。这个文件的变量在未预先
设置时才赋默认值；因此日常操作不得用 shell 环境覆盖镜像、存储或网络参数，
应修改源 YAML 后重新生成并审查 diff。

| 变量 | 来源/含义 | 操作约束 |
| --- | --- | --- |
| `TEMPLATE_BUILD_ENV` | 要 source 的 generated env 文件，Make 默认指向上述路径。 | 通常不覆盖；替换文件须经同等审查。 |
| `TEMPLATE_VMID`、`TEMPLATE_NAME` | 模板标识。 | VMID 须在 helper 限制的 `9000–9500`；名称匹配保守字符规则。 |
| `IMAGE_URL`、`IMAGE_SHA512`、`IMAGE_URL_PREFIX` | Debian genericcloud 下载地址、128 位十六进制 SHA-512、允许 URL 前缀。 | 三者共同界定镜像身份和下载边界；不得只换 URL 或跳过 checksum。 |
| `IMPORT_STORAGE`、`DISK_STORAGE` | 下载/导入与最终磁盘使用的 PVE datastore。 | 必须与源配置的 storage role 和内容能力一致。 |
| `BUILD_DOMAIN` | 模板构建时使用的域。 | 不等于某个 VM 的最终 hostname/FQDN。 |
| `APT_MIRROR`、`APT_SECURITY_MIRROR` | 模板镜像内 Debian 主与安全软件源。 | 仅影响新模板；既有来宾的软件源见第 4 章。 |
| `TIMEZONE`、`LOCALE`、`CIUSER`、`NAMESERVER` | 模板初始时区、locale、cloud-init 默认用户和 resolver。 | 不含密码；仍应由源 YAML 统一变更。 |
| `BUILD_BRIDGE` | 模板构建时临时网卡附着的既有 PVE bridge。 | helper 不创建 bridge；在线构建前确认其实际存在和 egress。 |
| `PVE_HOST`、`PVE_USER` | 本次 SSH transport 的 build node 和用户。 | `PVE_HOST` 必填且必须明确；`PVE_USER` 默认 `pve-ops`。 |
| `FORCE_REPLACE` | 为 `true` 时允许 wrapper 替换已有 template。 | 破坏性开关；默认 `false`，只能在已核对 VMID、备份与恢复路径后临时设置。 |
| `TEMPLATE_DEBUG` 或 `DEBUG` | 输出 wrapper 调试信息。 | 默认 `false`；禁止让调试输出携带运行时秘密。 |

`cluster.automation.cloud_init` 的关键字段如下：

| 路径 | 含义 | 约束/影响 |
| --- | --- | --- |
| `defaults.package_update` / `package_upgrade` | 首次启动的包更新策略。 | 当前安全默认是 `false`；维护由模板或 Ansible 承担。 |
| `defaults.ssh_pwauth` | SSH 密码认证开关。 | 当前应为 `false`。 |
| `defaults.disable_root` | 禁止 root SSH/登录的 cloud-init 策略。 | 当前应为 `true`。 |
| `drive_storage_role` | cloud-init drive 的 storage role。 | 必须可承载 `disk`。 |
| `snippet_storage_role` | user-data/network-config snippet 的 role。 | 必须可承载 `snippets`。 |
| `snippet_file_prefix` | 稳定 snippet 文件名前缀。 | 只能使用受限安全字符；派生文件不可手改。 |
| `users[]` | 初始用户。 | 每项需 `name`、`gecos`、`groups`、`shell`、`sudo`、`password_env`、`public_key_env`；后两者是变量名而非秘密。 |

当前约定中 `clemon` 是人工管理用户，保留密码受保护 sudo；`ops` 是自动化用户，
具有非交互 sudo。两者的密码和公钥由 runtime 环境在渲染时提供，绝不进入
inventory 或生成物。

### VM 默认值、模板与 PCI mapping

`vm_defaults` 提供 `cores`、`memory_mib`、`root_disk_gib`、`cpu_type`、`bios`、
`machine`、`clone_mode`、`scsi_controller`、`primary_disk`、`primary_nics` 和
`pool`；VM 可只覆盖资源/存储允许字段。`templates.<key>` 定义模板的 `vmid`、
`name`、`architecture`、`node`、`storage_role`、`source_storage_role`、
`disk_size_gib` 以及同类硬件/clone 参数。模板 VMID 必须落入 template 区间。

`pci_mappings.<mapping>` 包含 `type`、`ha_allowed`、默认 `pcie`/`rombar`/`xvga`
以及每个 PVE 节点的 `path`、`iommu_group`。它是消费既有 PVE resource mapping
的声明；正常 VM lifecycle 不创建 mapping、IOMMU、VFIO 或 host kernel 参数。

## 3.5 `vms.yml` 参数

每项 VM 使用以下根字段：

| 字段 | 含义 | 约束/影响 |
| --- | --- | --- |
| `name` | 稳定 VM 名称。 | 必须唯一；也是 generated inventory host 名。 |
| `vmid` | PVE VMID。 | 必须唯一且符合 `lifecycle_class` 的保留区间。 |
| `lifecycle_class` | `ephemeral_lab` 或 `long_lived`。 | long-lived 默认受 destroy 保护；不可借由重命名绕过。 |
| `node` | 目标 PVE 节点。 | 必须在 `pve-cluster.yml` 的 nodes 中。 |
| `template` | 可选 template key。 | 省略时用 `cluster.default_template`。 |
| `nics` | VM NIC 列表。 | 必须显式提供；详见下表。 |
| `resources` | 可选 `cores`、`memory_mib`、`root_disk_gib` 覆盖。 | 必须为正整数。 |
| `storage.disk_role` | 可选根盘 storage role 覆盖。 | 必须声明且可承载 disk。 |
| `ansible_groups` / `tags` | 生成 inventory 组和 PVE tags。 | 仅声明用途，不配置业务。 |
| `pool` | 可选 PVE pool。 | `null` 或字符串。 |
| `boot.started` / `boot.on_boot` | apply 后启动及宿主机启动策略。 | 显式布尔；long-lived 的默认 on-boot 政策来自生命周期。 |
| `ha.enabled` / `group` / `state` | HA 声明。 | passthrough VM 必须禁用 HA。 |
| `passthrough` | PCI mapping 消费声明。 | `null` 或受限 device 列表；见下文。 |

### NIC 参数

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `name` | 来宾内稳定 NIC 名称。 | 同一 VM 中唯一；K3s 用其选择的 role，不能自动猜接口。 |
| `role` | 网络职责，如 `management`、`cluster`、`storage`、`ingress`。 | 必须为校验器支持的角色；角色本身不创建网络策略。 |
| `network` | `pve-cluster.yml.networks` 的逻辑网络名。 | 只能引用 `attach_vms: true` 的网络。 |
| `macaddr` 或 `mac_address` | 确定性 MAC。 | 全环境唯一；cloud-init 按 MAC 匹配并命名 NIC。 |
| `static_ip` | CIDR 格式静态地址。 | 必须位于引用网络内且全局唯一。 |
| `gateway` | 此 NIC 的网关。 | 仅默认路由 NIC 应声明；必须匹配网络策略。 |
| `dns` | 此 NIC 使用的 resolver 列表。 | 用于 cloud-init 和来宾核验。 |
| `default_route` | 是否承载默认路由。 | 每 VM 至多一个。K3s phase-one 应仅为 `mgmt0`。 |
| `ansible_connection` | 是否为 Ansible SSH 连接 NIC。 | 每 VM 至多一个；其 IP 必须与生成的 `ansible_host` 一致。 |

K3s 目标多 NIC 约定为：`mgmt0` 负责 SSH/Ansible 与默认路由，`cluster0` 负责
K3s node identity/etcd/Cilium underlay，`storage0` 负责 TrueNAS 路径，`ingress0`
负责 Gateway/VIP。当前 Astra 源 inventory 尚未声明这样的 K3s VM；不能把普通
单 NIC VM 当作已具备该拓扑。

### Passthrough 参数

每项为 `mapping`，可选 `device_override`、`pcie`、`rombar`、`xvga`。`mapping`
必须引用 `pci_mappings`；同一 node/mapping 不能分配给多个 VM；passthrough VM
必须 HA disabled、使用适配的 `q35`/`ovmf`/`host` 硬件，并在 apply 前由人工确认
IOMMU/VFIO/设备绑定。`make pve-preflight` 会只读检查 mapping，不会配置 host。

## 3.6 模板、计划和 VM 生命周期

模板构建是变更操作。PVE 节点必须已安装 wrapper、`libguestfs-tools` 等依赖，
`build_bridge` 必须存在。它下载/复用缓存的 qcow2、校验 SHA-512、清理机器身份、
导入磁盘和转为 template；不将 VM 专用 IP、hostname、SSH host key 或应用秘密
写入模板。

构建过程使用生成的 `environments/astra/generated/packer/debian-13.env`；直接
调用 helper 时必须显式设置 `TEMPLATE_BUILD_ENV`。`PVE_HOST` 始终是明确的 build
node SSH host/IP。远端缓存位于 `/var/cache/astra/packer`，模板命名为
`debian-13-tmpl-YYYYMMDD`。wrapper 会写临时 deb822 source、删除旧
`/etc/apt/sources.list`、执行 APT 更新、安装 cloud-init、清理 cloud-init logs 并
通过 virt-sysprep 移除机器特有状态；这些仅发生在模板构建机/镜像内，不能代替
已有 VM 的 egress policy。对 OVMF/q35，模板有显式 4 MiB EFI disk；`qm importdisk`
会以实际 VM config 报告的 imported volume 附着，无法确定时失败而不是猜测。

```bash
# 需显式的 PVE runtime context，以及经确认的 PVE_HOST。
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- \
  make pve-packer-build PVE_HOST=<pve-management-host-or-ip>

# 在线只读：分别用于健康与 apply 前置条件。
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-health
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- make pve-preflight

# 变更前计划；STORAGE_ID 指 snippet upload 与验证所需的目标存储。
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- \
  make pve-plan STORAGE_ID=images
```

审查计划时逐项确认 clone 源、VMID、节点、storage、NIC bridge/MAC、cloud-init
snippet、long-lived destroy protection、启动策略与 passthrough。仅在这些项目和
恢复路径都明确后执行：

```bash
op run --env-file environments/astra/runtime/.env.pve-opentofu.tpl -- \
  make pve-apply STORAGE_ID=images
```

`pve-apply` 会渲染、上传并验证 cloud-init snippets，并在 apply 前后备份本地
OpenTofu state 到忽略的 `.cache/tofu-state-backups/`。state 位于
`environments/astra/opentofu/pve/terraform.tfstate`，是单操作者本地状态；不得
提交、复制到 issue 或用删除 state 的方式修复漂移。

同样受保护的本地路径包括 `.cache/pve-cloud-init/user-data/`（cloud-init 渲染
输出和 manifest/checksum）与 `.cache/packer/`（本地 Packer cache）。它们是
可删除重建的运行数据，但不得在仍有相关工作流运行时自动清理，也不得作为新
PVE root 的隐式 state 输入。

`make pve-destroy` 是显式破坏性命令。即使目标是 ephemeral VM，也必须单独核对
实际 VMID、state、备份、服务依赖和销毁范围；long-lived 保护不是授权绕过。

创建后运行：

```bash
make pve-verify-guests
```

该命令在线只读检查 generated inventory 假设、SSH/sudo、hostname、静态 IP、
resolver、qemu-guest-agent 和 root SSH 边界。离线或 DNS 不匹配会被报告为
`WARN`；不能把 WARN/未连通来宾作为合格 K3s 宿主机。

## 3.7 PVE 维护与恢复

PVE maintenance 没有自动迁移、停止 VM、更新系统包、重启节点或修改 Ceph flag
的工作流。每次窗口应：

1. 记录节点、窗口、工作负载、备份、控制台、容量和 passthrough 限制；
2. 运行 `make pve-health`，必要时运行 `make pve-verify-guests` 形成基线；
3. 依据实际 live quorum 和剩余容量选择单节点停机或逐节点维护，不能从 YAML
   节点数推断 HA；
4. 对每个 VM 记录迁移、受控关机或延期决定；passthrough VM 通常需要停机；
5. 每次只维护一个节点，回归后立即重跑健康检查；出现 `FAIL`、不可解释告警、
   存储/锁/VM 状态异常或控制台不可用即停止；
6. 窗口结束后保存健康、VM 状态、实际操作和接受告警。

如果 Ceph 已配置或其状态无法确认，必须使用独立的环境专用 Ceph 维护方案；
不要从本手册推导 `noout` 或其他 Ceph mutation。PVE 维护与 PCI 准入操作均以
本章为现行路径。
