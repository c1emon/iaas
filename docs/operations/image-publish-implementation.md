# 镜像构建与 PVE 发布：双仓实施记录

## 当前范围

2026-09-23 开始实施，主 agent 负责合同协调和联合验收，两仓各有独立实施 agent。
用户授权创建实施分支、保留工作树修改、持续实施与分阶段提交。

| 仓库 | 实施分支 | 变更 |
| --- | --- | --- |
| iaas | `feat/separate-image-build-and-pve-publish` | [change](../../openspec/changes/separate-image-build-and-pve-publish/proposal.md) |
| infra-ops | `feat/integrate-image-build-and-pve-publish` | [change](../../../infra-ops/openspec/changes/integrate-image-build-and-pve-publish/proposal.md) |

共用字段与结果语义以 [权威合同](../../openspec/changes/separate-image-build-and-pve-publish/contracts/image-publish-v1.md) 为准。
合同缺口由主 agent 协调修改；各仓内部实现独立推进。任务只有取得对应范围的证据才勾选。
infra-ops 原有 `docs/operations/README.md` 修改与未跟踪的 `pve-ci-iaas-handoff.md` 保留，尚未纳入本次提交。

## 阶段与证据

| 阶段 | 状态 | 证据或限制 |
| --- | --- | --- |
| 实施分支 | 已完成 | 两仓已从原 HEAD 创建对应分支，工作树修改保留 |
| iaas 前置规格归档及软件实现 | 进行中 | 由 iaas 实施 agent 验证和记录 |
| infra-ops 软件接入 | 进行中 | 由 infra-ops 实施 agent 验证和记录 |
| 跨仓实际入口联调 | 待执行 | 需要可调用的新版 runtime 与明确版本绑定 |
| amd64/KVM 构建及来宾检查 | 待执行 | 本机不符合执行器条件；专用执行器尚待确定 |
| PVE 发布、临时 VM 与清理 | 待执行 | HTTPS 服务已修复并只读验证；现场窗口尚未安排 |

首次跨仓软件交接检查：同一 `image-artifact/v1` 描述（external 来源、unknown 检查、`evidence_ref: null`）分别通过两仓当前校验器，输出相同规范化摘要。此检查未读取真实磁盘，只覆盖该代表性描述的字段与摘要交接，不代表全部 schema 或发布入口联调完成。

## 本轮只读现场观察

以下是 2026-09-23 的一次观察，不是持续有效的服务状态保证。

- 本机为 Darwin ARM64，当前 Colima Docker 返回 Linux aarch64；不能用其替代要求的 Linux amd64/KVM 构建验收。
- 初次核对时短名称 `cohe` 不能解析，仓库登记的管理 IP 可通过严格 host-key 校验的 SSH 读取。用户随后提供管理域名 `cohe.mgmt.int.clemon.icu`；再次核对确认 SSH alias `cohe` 已映射该域名和 root 用户，并成功连接。
- 节点返回 Linux x86_64、PVE manager `9.2.11`、storage library `9.1.10`、qemu-server `9.2.7`；存在 `/dev/kvm`。这不证明专用构建执行器已部署，也不证明 KVM 来宾启动成功。
- 安装版 `Storage/Status.pm` 确认 upload 接受 `content=import` 和 SHA-256 checksum，并返回原生任务标识；`Storage/Content.pm` 确认 import 删除要求 `Datastore.Allocate`，默认返回任务标识，指定 delay 时可返回成功 null。
- 安装版 Qemu API 支持 `<destination-storage>:0,import-from=<source-volume-id>`。源码检查证明接口声明和实现存在，不证明当前 token 权限或实际后端操作成功。
- HTTPS 存储 GET 探测失败。随后 `systemctl is-active pveproxy pvedaemon` 分别返回 `failed`、`active`，`ss` 未发现 8006 监听。未重启服务、修改插件、安装 helper 或写入 PVE 资源。
- 定向日志分类与路径核对显示 pveproxy 对 `/var/lock/pveproxy.lck` 的访问被拒绝；实际 `/run/lock` 为 `root:root 0700`，锁文件为 `www-data:www-data 0644`。系统 `debian.conf` 声明 `/run/lock 1777`，`legacy.conf` 声明 `0755`，两者均不同于现场 `0700`。

## 已授权的 HTTPS 故障修复

用户随后明确授权修复并验证。已将 `/run/lock` 恢复为 `root:root 1777`，清除 pveproxy 的失败状态并启动服务。观察到 `ActiveState=active`、`SubState=running`、`Result=success` 和 8006 监听。

通过现有只读、证书校验的 HTTPS GET 探针依次读取三个存储：

| 存储 | 类型 | 内容能力 | 状态 |
| --- | --- | --- | --- |
| local | dir | vztmpl | active/enabled |
| images | nfs | iso,backup,import,snippets | active/enabled |
| memory | truenas | images | active/enabled |

这证明当前安装版存储 GET 可用，TrueNAS 日志未破坏本次 HTTPS JSON；不证明新版发布 token 的 ACL 或任何上传/导入写入。未创建或修改模板、VM、存储定义，未修改 TrueNAS 插件。`local` 当前不支持 images，不能拿它充当目录磁盘验收环境。

用户提供的新管理域名可用于当前 SSH 连接；此时节点证书 SAN 仍包含 `cohe.base.clemon.cis`、`cohe`、`10.1.0.72`，不包含 `cohe.mgmt.int.clemon.icu`。HTTPS 需要选择证书覆盖的地址并提供相应 CA，或先正规更新证书，不能把 SSH 域名直接当作已验证的 HTTPS 身份。

现场后续需明确专用 KVM 执行器和新测试窗口，再执行串行的单模板、单临时 VM 验收。旧窗口不作为本轮授权依据。软件替身与源码证据不替代以上现场任务。
