# 镜像构建与 PVE 发布：双仓实施记录

## 当前范围

2026-09-23 UTC 开始实施，主 agent 负责合同协调和联合验收，两仓各有独立实施 agent。
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
| 跨仓实际入口联调 | 软件范围通过 | Astra check、请求规范化、完整准入及发布/清理替身入口已验证；现场写入已有限定证据，正式 runtime release pin 与站点启用仍未完成 |
| amd64/KVM 构建及来宾检查 | 已完成限定范围 | ONE Linux amd64/Docker/KVM 上 r7 build 与 r2 独立 test 真实通过；不代表持久 Forgejo Runner、发布镜像 pin 或 PVE 验收 |
| PVE 发布、临时 VM 与清理 | 已完成限定范围 | r8 模板发布、retire、VM799 清理及 S3 cleanup 均有受限现场证据；5.4 正式 runtime release handoff 仍未完成 |

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

本阶段软件验证（现场窗口前）：`uv run pytest -q` 为 **1639 passed**（一条既有 crypt 弃用警告）；launcher `go test ./...`、完整 pyright、相应 Ruff 规则、OpenSpec strict 与 staged diff 检查通过。GitNexus 完整变更分析覆盖 224 个符号、18 条执行流，无 partial/truncated；整体风险为 critical，主要涉及 launcher 输入/输出、发布及清理入口，不以图查询代替以上测试。最终构建器在禁网容器中确认 Packer 1.16.0、qemu-img、OVMF 与 runtime 导入可用；其临时目录需可写，不能把整个容器只读且不给 `/tmp`。该软件阶段检查本身不提供现场 KVM 来宾证据；ONE 现场证据见下文。

## 本轮只读现场观察

以下是 2026-09-23 的一次观察，不是持续有效的服务状态保证。

- 本机为 Darwin ARM64，当前 Colima Docker 返回 Linux aarch64；不能用其替代要求的 Linux amd64/KVM 构建验收。
- 初次核对时短名称 `cohe` 不能解析，仓库登记的管理 IP 可通过严格 host-key 校验的 SSH 读取。用户随后提供管理域名 `cohe.mgmt.int.clemon.icu`；再次核对确认 SSH alias `cohe` 已映射该域名和 root 用户，并成功连接。
- 节点返回 Linux x86_64、PVE manager `9.2.11`、storage library `9.1.10`、qemu-server `9.2.7`；存在 `/dev/kvm`。这条只读观察不证明专用构建执行器已部署或 KVM 来宾启动成功；现场构建证据另行记录。
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

## 2026-09-23 本轮实现与证据边界

- `d1c4bd0` 修复了 image test 在只读输入挂载上的 qemu 元数据检查：`qemu-img` 的 JSON 捕获临时文件改写入任务的可写 `outputs/work`，不再尝试写入 `/inputs/files/...` 等只读源目录。新增代表性只读源回归后，image execution 定向测试为 22 passed，runtime Pyright 与 Ruff 通过。
- 本轮失败样例发生在来宾启动前，原因是捕获文件目录不可写；同一只读绑定上的独立 `qemu-img info` 已确认可读。该修复不放宽输入挂载权限，也不证明来宾启动或测试验收成功。
- 当前 image 任务材料的实际布局是 `work/image-tasks/<execution-id>/artifact.json`、`disk.qcow2`、`disk.qcow2.sha256`、`build-result.json`，以及测试产生的 `test-result.json`；操作文档已按此路径修正。`generated/` 下的 `template-record.json` 仍仅属于 PVE 发布结果。
- 本轮 buildfix8 已形成 5.2 的真实证据；此前“正在执行”的中间状态已由下列结果替代。该证据不勾选 PVE 发布、临时 VM 或清理终验任务。

## 5.2 amd64/KVM 真实验收

2026-09-23，调用方在 ONE 上以 Linux amd64 Docker/KVM 执行器完成一项 build 和一项独立 test。build 使用 execution `one-build-20260923-0003-r7`，artifact 的磁盘摘要为 `sha256:891e603a57be75b995491f3d9fd9d1b9a0cca11891245d72c4d4c418f9341cb9`；format、self-contained、identity-cleanup、first-boot 均 passed，官方 cleanup 返回 succeeded 且 residue 为空。对应 image-builder runtime digest 为 `iaas-image-builder@sha256:e0924f6796dd10da7db85ed1397b3511a39f71120b8784b98fd99561daaf60a9`。

独立 test 使用 execution `one-test-20260923-0003-r2`，消费同一磁盘摘要；first-boot、cloud-init、guest-agent 均 passed，`base_unchanged=true`，cleanup 为 succeeded 且 residue 为空。对应 runtime digest 为 `iaas-image-builder@sha256:8ff32e662b511778039634107f7a4e3ffbf205118bee5ecbebf71937cab04791`。两次操作均由官方 task cleanup 完成。

执行边界为 ONE 上的 Linux amd64 Docker 容器和 `/dev/kvm`；实际 builder 子容器使用只读根、可用 KVM，未提供 Docker socket、PVE 凭据、S3 凭据或 1Password 凭据。该证据证明本次调用方提供的执行器和这两个 execution 的来宾路径，不证明持久 Forgejo Runner 已部署，也不证明 runtime 已发布或 PVE 模板已创建。PVE 现场证据见下一节；本节仅记录 5.2。

## 2026-09-23 PVE 现场限定证据

本轮在同一受控窗口完成了一次模板发布和一次临时 VM 生命周期，证据仍受调用方执行器、当前 runtime digest 及现场权限范围约束。模板发布使用 execution `pve-live-apply-20260923-0003-r8`，runtime 为 `iaas-runtime@sha256:16b3f3f7093ed51576d0220d51f93180ccfe2259835cd7eef675cf1d4ee8f39a`，artifact 为 `sha256:5a07381782f8f5578ef2a8ff2bfb2a3b97f50d9ea76a9e9354cc25d15caf550f`。原生 upload、create、import-config、template 均 succeeded，发布结果、collection 和 staging cleanup 均 succeeded，residue 为空；生成模板为 VMID 9003。该步骤没有启动来宾，因此不提供 guest boot 或 guest acceptance 证据。

VM799 使用 execution `vm799-create-20260923-0003-r2` 完成原生 apply，`native_execution`、state persistence 和 collection 均 passed，来宾保持 `started=false`，没有执行 guest boot。原始结果的配置验证仅因 PVE 省略默认 `bios` 字段而为 unknown；提交 `2c0c3e5` 后，使用当前源码对同一实际配置做只读复核，2026-09-23 05:32:36 所有配置检查均 passed。该复核不改写原始 execution 结果，原结果继续保留 failed，并由调用方标记 manually reconciled。

随后 VM799 destroy execution `vm799-destroy-20260923-0003` 的原生操作、collection、state persistence 和 absence verification 均 passed；state serial 为 2、state 为空、资源数为 0。现场 fresh API observation 确认 VM 已 absent，`snippet-cleanup.json` 记录的两份临时 snippet 已删除。该清理证据覆盖本次授权的 VM 与 snippet 资源，不扩展为整站存储穷举。

模板 retirement execution `pve-live-retire-20260923-0003` 的 native 与 Engine 结果均 succeeded，residue 为空。2026-09-23 05:42:36 的 after-retire observation 返回 `test_vmids=[]`、`storage_volumes=[]`；临时角色 `IaasLiveUpload20260923` 已撤销，`iaas-test-dir` storage definition 与空目录已删除，证据记录于 `test-storage-cleanup.json`。S3 image cleanup 随后以 `image-cleanup-delete-result.json` 完成，状态为 `cleaned`，删除四个精确对象且 `independent_prefix_empty=true`；`s3-task-grant-revoke.json` 确认临时 task grant 已移除并保留其他六条 statements。

旧入口退役证据 `legacy-template-helper-uninstall.json` 确认四个旧文件已删除、snippet helper 保留、visudo 校验通过且 packages 未变化。TrueNAS `Helpers.pm` 保持原 stdout 设置；pveproxy 仍 active/running，`/run/lock` 为 `1777`。这些证据覆盖本次授权的旧入口、PVE 测试资源和 image 对象，不扩展为整站资源穷举。

2026-09-23 05:45:59 UTC 的 production 9001 final observation 显示对象 unchanged 且 HTTPS healthy；private copy 与 8 个 locator 已清除。该观察不改变本轮 PVE 资源范围；S3 cleanup 已由上述独立结果完成。

ONE image execution 已有 guest boot evidence；PVE VM799 本轮保持 `started=false`，没有执行 guest boot。当前证据不包含正式 OCI/runtime release 或持久 Forgejo Runner 部署；这些边界仍保持未完成。5.3 已在本轮限定范围内完成，证据覆盖模板发布、VM 生命周期、retire、S3 cleanup 和现场无残留核对；5.4 release handoff 仍未授权发布或标记完成。

## OCI 打包与 Python 包边界

普通 OCI 镜像的打包材料位于 `automation/oci/iaas-runtime/`，磁盘镜像构建执行器的
打包材料位于 `automation/oci/disk-image-builder/`。两者共享 `oci/common/` 的入口和
依赖清单；构建后的检查位于 `oci/checks/`，共同发布逻辑位于 `oci/release.py`。
Python 实现位于仓库根目录的 `src/iaas/`，模块入口已由 `iaas_automation.*` 改为
`iaas.*`。这是源码/命令入口的不兼容改名；本轮未发布新的 OCI 镜像，也未改变已留存的
现场执行证据。

## PVE bootstrap 用户由调用方选择

`automation/ansible/playbooks/pve/bootstrap-pve-ssh-user.yml` 要求调用方提供
`pve_bootstrap_user` 和 `pve_bootstrap_authorized_key`，不再由 IaaS 选择账号。
playbook 用同一用户名创建 SSH 账号并渲染 snippet-upload sudoers 规则，SSH
目录取系统返回的实际 home。此处是软件和合同修正；本轮没有修改现场用户或权限。
