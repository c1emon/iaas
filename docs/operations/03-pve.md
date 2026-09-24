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
| `$ENVIRONMENT_DIR/inventory/pve-cluster.yml` | PVE 集群共享事实、模板、网络、存储角色、VM 默认值和 PCI mappings。 | 归一化模型、OpenTofu input、Ansible inventory、PVE VM 文档。 |
| `$ENVIRONMENT_DIR/inventory/vms.yml` | 单个 VM 的生命周期、NIC、资源、启动、HA 与 passthrough。 | 同上。 |
| `$GENERATED_DIR/opentofu/pve.tfvars.json` | 生成的 OpenTofu 输入。 | 只审查，不手改。 |
| `$GENERATED_DIR/ansible/pve.yml` | 生成的 VM SSH/网络事实。 | VM bootstrap、guest verify、K3s inventory 输入。 |
| `$GENERATED_DIR/docs/pve-vms.md` | VM 声明的可读表格。 | 审查参考，不是源配置。 |
| `$PVE_ENV_TEMPLATE` | PVE API、SSH 和 cloud-init 用户材料的运行时变量名。 | 调用方通过 1Password 或传统 Secret 注入相同变量。 |

本章示例从仓库根目录执行，先显式选择目录：

```bash
export ENVIRONMENT_DIR=/absolute/environment
export OUTPUT_DIR=/absolute/output
export GENERATED_DIR="$OUTPUT_DIR/generated"
export PVE_DIR=/absolute/opentofu-root
```

后续 Make 命令继承以上目录。切换终端后重新设置；其他环境使用对应绝对路径。
凭证来源见 [运行时凭据约定](00-preparation-and-conventions.md#04-运行时凭据与文件权限)。

先运行：

```bash
make pve-check
make pve-ansible-syntax
make pve-bootstrap-guests-syntax
```

`pve-check` 只校验源与已提交生成物是否一致；不检查实际 PVE bridge、存储、模板
或来宾可达性。

## 3.3 PVE template publisher and retained snippet helper

Image construction runs as the independent local `image` capability. Template
publication runs in the controller through the HTTPS PVE API and consumes an
`image-artifact/v1` plus `pve-template-publish-request/v1`; it does not install
or invoke a node template worker, storage probe, Packer PVE builder or template
sudo rule. Supply the fixed API endpoint with a matching CA, an operation-scoped
`PVE_API_TOKEN`, and a protected `PVE_ARTIFACT_URL` locator resolved for the
credential-free HTTPS or S3 request source. The publisher checks VMID, storage activity/content and
known capacity before downloading and verifies the final bytes, qcow2 format,
virtual size and absence of a backing file before its first PVE write.

The apply sequence is upload with `content=import` and SHA-256, create VM,
`importdisk` from the selected storage volume, configure boot/cloud-init/EFI,
convert to template, wait for every returned UPID, and independently verify
current configuration and attached volumes. PVE temporary upload space and
reverse-proxy limits are reported as unobserved unless the API exposes them;
SSH is not added to probe them. Cleanup and retire use new action-specific
previews with current publisher ownership, task inactivity and caller
retirement/dependency admission. A failed or unknown native task remains
pending and is never treated as a successful publication.

The independent `iaas-pve-snippet-upload` helper remains available only for
cloud-init snippet transfer where the selected VM workflow requires it. Its
SSH key and known_hosts are separate operation inputs; it is not a template
build or publication transport.

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

### 独立镜像与模板发布

Debian 镜像由独立 `image` capability 构建和测试，产出
`image-artifact/v1`。PVE 模板由控制端 `pve-template` HTTPS publisher
消费该 artifact 和 `pve-template-publish-request/v1`；模板 VMID、节点、存储、
bridge、固件与 cloud-init 默认值都属于发布请求，不再写入 PVE VM inventory。
请求、preview、execution admission 和 result 的固定字段见
[image publication contract](../contracts/image-publish-v1.md)。PVE inventory
仍只描述 OpenTofu 管理的模板引用和普通 VM，生成器不会输出构建环境文件。

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

初始用户名称、sudo 策略和凭据变量名由调用方的 `users[]` 声明。密码和公钥
由调用方在渲染时提供；秘密不能写入 inventory 或非敏感生成物。

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
负责 Gateway/VIP。这是受支持的多 NIC 设计示例，实际节点由调用方声明；
不能把普通单 NIC VM 当作已具备该拓扑。

### Passthrough 参数

每项为 `mapping`，可选 `device_override`、`pcie`、`rombar`、`xvga`。`mapping`
必须引用 `pci_mappings`；同一 node/mapping 不能分配给多个 VM；passthrough VM
必须 HA disabled、使用适配的 `q35`/`ovmf`/`host` 硬件，并在 apply 前由人工确认
IOMMU/VFIO/设备绑定。`make pve-preflight` 会只读检查 mapping，不会配置 host。

## 3.6 模板、计划和 VM 生命周期

镜像构建由独立 `image` capability 在明确的 QEMU/KVM executor 上完成，
并在交付前记录磁盘摘要、自包含性和清理证据。模板发布消费固定的
`image-artifact/v1` 和 `pve-template-publish-request/v1`，由控制端 HTTPS
publisher 完成上传、VM 创建、importdisk、cloud-init/EFI 配置、template 转换
和 API 读回核验。发布不使用节点 template worker、Packer PVE token 或存储
space probe；snippet transfer 仍是普通 VM 工作流的独立 SSH helper。

正式写入入口统一使用 [`iaas run` 启动器](../runtime-launcher.md) 的
`pve-template` 或 PVE `read` / `plan` / `apply` / `verify`。调用方为模板发布
选择 request、artifact locator、PVE API CA、API token、preview 和完整
execution admission；它们独立于 VM root、OpenTofu state 和 SSH snippet 凭据。

```bash
iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation read \
  --scope <root-id> --output ./pve-read

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation plan \
  --scope <root-id> --output ./pve-plan

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation apply \
  --scope <root-id> --execution-id <execution-id> \
  --plan ./pve-plan/plan/plan.tfplan --companions ./pve-plan/plan \
  --output ./<execution-id>

iaas run --runtime-config runtime.json --environment environment.yml \
  --engine local --component pve --operation verify \
  --scope <root-id> --plan ./pve-plan/plan/plan.tfplan \
  --companions ./pve-plan/plan --output ./pve-verify
```

审查计划时逐项确认 clone 源、VMID、节点、storage、NIC bridge/MAC、cloud-init
snippet、long-lived destroy protection、启动策略与 passthrough。删除通过
`components.pve.options.destroy: true` 生成普通 delete plan，仍需新的
execution admission 和显式 apply；`make pve-plan`、`make pve-apply`、
`make pve-destroy`、`make pve-packer-build` 和 `make upload-cloud-init` 已关闭，
调用时返回迁移错误。旧本地 state、旧 helper 路径和旧写入命令不会自动迁移。

`pve-verify-guests` 可作为来宾侧只读检查，但不能替代运行时的 native plan
verification、PVE API 读回或 caller acceptance。模板构建/清理的具体命令与
synthetic root 见 [PVE 生命周期示例](../examples/pve-lifecycle/README.md)。

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
