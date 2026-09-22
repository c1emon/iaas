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
| iaas 前置规格归档及软件实现 | 已完成软件阶段 | 主流程、失败恢复、隔离及发布接入已实现；全量软件检查通过 |
| infra-ops 软件接入 | 已完成软件接入 | 当前阶段提交 `5944fbf`；站点启用仍未执行 |
| 跨仓实际入口联调 | 软件范围通过 | Astra check、请求规范化、完整准入及发布/清理替身入口已验证；最终 runtime pin 和现场写入尚待完成 |
| amd64/KVM 构建及来宾检查 | 待执行 | 本机不符合执行器条件；专用执行器尚待确定 |
| PVE 发布、临时 VM 与清理 | 待执行 | HTTPS 服务已修复并只读验证；现场窗口尚未安排 |

首次跨仓软件交接检查：同一 `image-artifact/v1` 描述（external 来源、unknown 检查、`evidence_ref: null`）分别通过两仓当前校验器，输出相同规范化摘要。此检查未读取真实磁盘，只覆盖该代表性描述的字段与摘要交接，不代表全部 schema 或发布入口联调完成。

发布客户端的真实本地 HTTPS 回归已通过（`tests/python/test_pve_publish_https_client.py`，3 项）：POST 表单编码、证书信任与重定向拒绝、环境代理隔离，以及 import multipart 字段和有界文件读取。该检查使用临时本地 TLS 服务，不覆盖 PVE 原生任务、存储后端或现场权限。

同一发布请求分别经两仓校验器规范化，普通描述和附带独立测试结果两条路径均得到一致摘要。合同与本地 HTTPS 代表性回归共 9 项通过；这不代表发布副作用及恢复入口已经完成。

专用构建器 Dockerfile 已通过本地 `linux/amd64` BuildKit 构建；容器内 Python、Packer、qemu-img、virt-customize、OVMF 与来宾工具所需内核文件可用。在禁网容器中，Astra 的实际 request 经 `image check` 返回 success。初次启动因 Colima 空间不足失败，删除本次自有旧中间镜像后重试成功。该镜像是未发布的本地检查版本，最终代码和不可变 runtime pin 尚需同步；ARM 主机上的容器执行不证明 KVM 或来宾检查通过。

普通 runtime 已补充发布时需要的 qemu-img，并移出 Packer；Packer 保留在专用构建器中。普通 runtime 本地容器中，真实 qemu-img 生成的自包含磁盘通过检查，带 backing file 的磁盘被拒绝；镜像层检查确认排除内容与许可证保留符合现有规则。这些检查未运行来宾。

跨仓实际入口补充：Astra image request 经当前 IaaS `image check`、代表性发布请求经 `pve-template check` 均通过；infra-ops 生成的完整准入经过当前 IaaS admission validator，使用原生 preview 摘要去除显示前缀后的 64 位十六进制值。infra-ops 收尾提交为 `5336515`。这些入口为被动检查，没有调用 PVE 写入。

定向故障检查覆盖本地 TLS 上传收到 HTTP 413、下载写入注入 ENOSPC 后删除部分文件，以及远端清理未知与本地清理失败同时发生时保留未知状态。HTTP 413 使用本地 TLS 服务，ENOSPC 使用受控写入异常；均不作为现场存储故障演练证据。

最终复核补齐了原始 UPID 历史保留、完整 VM 附件绑定、创建前固定 SMBIOS UUID，以及完整模板只允许 retire 的边界。使用实际 `_publish` 产出的失败 journal 验证后续 cleanup，并覆盖模板已完成但首次暂存区观察失败时的 staging-only 恢复。当前对象 read 无需构建材料；verify 被动检查结果与原 preview 的绑定，不能通过新观察补造历史成功。

release 软件流程已接入同一 tag 的普通 runtime（amd64/arm64）和 image-builder（amd64），沿用已测镜像、不覆盖已有版本及匿名按摘要消费检查。本地最终两个镜像均已刷新成功；尚未触发真实 release、推送镜像或取得可供站点使用的发布摘要。

后续跨仓交接修正已提交至 infra-ops `5944fbf`：PVE token 使用完整 `user@realm!token_id=secret` 格式，私有 CA 路径在环境搬运后保持原声明位置，读取各操作实际输出文件，并显式选择独立 image-builder runtime。28 项定向检查与接入当前 IaaS 校验器的 286 项 infra-ops 回归通过。站点 launcher 仍固定在 `v0.1.0-rc.12`，`runtime/image-builder.json` 尚无真实发布 pin；构建 workflow 会在缺少该配置时停止。这些材料尚不能当作已启用的新版本站点。

本阶段最终验证：`uv run pytest -q` 为 **1639 passed**（一条既有 crypt 弃用警告）；launcher `go test ./...`、完整 pyright、相应 Ruff 规则、OpenSpec strict 与 staged diff 检查通过。GitNexus 完整变更分析覆盖 224 个符号、18 条执行流，无 partial/truncated；整体风险为 critical，主要涉及 launcher 输入/输出、发布及清理入口，不以图查询代替以上测试。最终构建器在禁网容器中确认 Packer 1.16.0、qemu-img、OVMF 与 runtime 导入可用；其临时目录需可写，不能把整个容器只读且不给 `/tmp`。本次未运行 KVM 来宾。

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

后续源码定位确认原因：旧 `iaas-pve-template` 的 `lock(path)` 无条件执行 `path.parent.chmod(0o700)`；节点锁默认位于 `/run/lock`。已在保留的 `f98e5f9` 源码和节点当前安装文件中确认同一逻辑；复查 `/run/lock` 仍为修复后的 `1777`。本轮没有再调用旧 helper 的加锁操作，也没有超出已授权范围改写节点 helper。切换前调用方须停用旧任务准入，按迁移步骤退役旧入口，以防该旧逻辑再次改变共享目录权限。

通过现有只读、证书校验的 HTTPS GET 探针依次读取三个存储：

| 存储 | 类型 | 内容能力 | 状态 |
| --- | --- | --- | --- |
| local | dir | vztmpl | active/enabled |
| images | nfs | iso,backup,import,snippets | active/enabled |
| memory | truenas | images | active/enabled |

这证明当前安装版存储 GET 可用，TrueNAS 日志未破坏本次 HTTPS JSON；不证明新版发布 token 的 ACL 或任何上传/导入写入。未创建或修改模板、VM、存储定义，未修改 TrueNAS 插件。`local` 当前不支持 images，不能拿它充当目录磁盘验收环境。

用户提供的新管理域名可用于当前 SSH 连接；此时节点证书 SAN 仍包含 `cohe.base.clemon.cis`、`cohe`、`10.1.0.72`，不包含 `cohe.mgmt.int.clemon.icu`。HTTPS 需要选择证书覆盖的地址并提供相应 CA，或先正规更新证书，不能把 SSH 域名直接当作已验证的 HTTPS 身份。

随后从本机直接以节点公开 CA 验证 `https://10.1.0.72:8006/`，返回 HTTP 200。这补充了控制端到节点的 HTTPS 可达性证据；页面访问不等于发布 token 的授权验证。

现场后续需明确专用 KVM 执行器和新测试窗口，再执行串行的单模板、单临时 VM 验收。旧窗口不作为本轮授权依据。软件替身与源码证据不替代以上现场任务。
