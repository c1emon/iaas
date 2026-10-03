# Debian 13 通用模板交付

本次只实现当前合同，不增加旧版本兼容。软件、固定产物、真实构建/发布和克隆来宾检查已验证。常规清理的 PVE DELETE 失败，原生验收整体仍为未知；独立恢复已清除临时资源。不能据此开放日常部署。

## 固定版本与软件检查

源码 `ce18e213487741d9528657e745d08a1990a0c4dd`；[rc.31 Release](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.31)、[发布流水线](https://github.com/c1emon/iaas/actions/runs/37122581034) 七个作业全部通过。
amd64/arm64 各 `2199 passed, 4 skipped`，pyright 0 errors；实际镜像保存计划、匿名拉取/调用检查通过。
本地相关回归 940 passed，DNS/清理修复相关 92 passed，最终合同/示例同步检查 87 passed；当前 v3 恢复材料回归 102 passed。
真实构建和发布使用 [rc.28](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.28)（源码 `3f73d135aa75c462048b446cc79e1af3598c4f21`）；其构建传参修复相关 60 passed 与 Packer syntax-only 通过。

| 产物 | 固定引用 / SHA-256 |
| --- | --- |
| runtime rc.31（linux amd64/arm64，最终克隆/恢复） | `ghcr.io/c1emon/iaas-runtime@sha256:59793b1f5fa92b59958be8e34888b8b864114da802b8cd6e2e9cfa58578bc86f` |
| builder rc.31（linux amd64，需 KVM，发布软件检查） | `ghcr.io/c1emon/iaas-image-builder@sha256:877251b20783db37054310d83cf31c08b19b147e8f7b80af53c05b41fec1c0cf` |
| runtime rc.28（实际发布 9000） | `ghcr.io/c1emon/iaas-runtime@sha256:b94be20db28a7a7fc56f1186ad22610fb0df2ca8bcecd5a60e1d1e282d19aaab` |
| builder rc.28（实际 KVM 构建） | `ghcr.io/c1emon/iaas-image-builder@sha256:09651e0fb69c0741b7a9b86f0dc61e8ee6cab2b297f465a2297fc41a20d27f30` |
| iaas-darwin-arm64 rc.31 | `029e101e1d39552fe10198ae8589882b5f1a2ad27aabf7c0783d631ca52d9d19` |
| iaas-linux-amd64 rc.31 | `ba8784668167e342c3435bcdb3de73863f02b6e20a6431ea7007ee134294685c` |

ONE 已拉取并核对两个版本镜像的 digest、源码/版本标签；rc.31 两个 launcher 与 Release SHA256SUMS 一致，macOS/ONE launcher 均报告 rc.31。
rc.28→rc.31 的源码改动涉及验收观察器、清理查询、当前 v3 恢复材料校验及配套测试/文档，构建与发布逻辑相同；不把 rc.28 的真实构建记录改称 rc.31 构建。
schema 随该源码和镜像固定：build request/v2、publish request/v2、record/preview/result/v3、acceptance request/v3。

rc.27 真实构建在清华源刷新及包升级后因非空软件列表的 key=value 解析失败，未产生成功 artifact；rc.28 改用完整 JSON Ansible 参数并覆盖实际解析器正反例。
原始失败日志、执行 summary 和失败任务状态保留；原生 image clean 已清除其临时盘、seed 和构建密钥（也删除了任务内 build-result.json）。后续验收不改写这次失败结论。

## 真实主线

ONE/KVM 的 `debian13-build-rc28` 成功，artifact 的七项检查通过（record 中 scope 为 static）；另有实际临时开机、cloud-init/QGA 检查日志和后续 PVE 克隆来宾证据，不把静态 scope 字段当作现场验收。基础盘固定为 Debian 官方
`20260601-2496` amd64 genericcloud，官方 SHA-512 校验通过。启用清华 Debian/security 源和
构建时 dist-upgrade，安装七项基础工具及 cloud-init/cloud-guest-utils/QGA；离线收尾清理身份、
构建账户/密钥及临时网络。最终 qcow2 虚拟容量 `8589934592` 字节，物理大小 `1570242560` 字节，
SHA-256 `592cb62ac7471e83eb55a55d94c692412f590b8221edd234de8ebe600c41eaa8`。
镜像内只读检查确认 Debian 13、清华源和自动扩容/网络初始化能力；已安装版本包括
cloud-init `25.1.4-1+deb13u1`、QGA `1:10.0.13+ds-0+deb13u1`。

原生发布 `debian13-publish-rc28-uid1000` 成功：模板 9000、2 CPU、1024 MiB、
`memory:base-9000-disk-0,size=8G`，无任何 `netN`。暂存存储使用有上传/删除权限的 `local`，
系统盘/cloud-init 盘使用 `memory`；发布验证、record/v3 和暂存上传清理均成功。

首轮 `debian13-accept-rc28` 在既有 `iaas-acceptance` 池完整克隆 VM500，先配置网络、独立
身份和扩盘后启动。根盘 `137438953472`、根分区 `137304718848`、文件系统 `135061168128`
字节；地址/网关、cloud-init 和 QGA 正常，源模板不变。但旧观察器仅看到 `127.0.0.53`，
DNS 检查失败；删除后的存储清单 HTTP500 使卷清理结论未知。原结果仍保留失败/未知。
后续独立只读观察确认 VM500、其两盘均不存在，源模板不变；不据此改写原结果。

rc.30 与 rc.31 新执行的六项来宾/源检查全部通过。最终 `debian13-accept-rc31` 在既有
`iaas-acceptance` 池完整克隆 VM500，8 CPU/8192 MiB、`memory` 盘；首次启动前添加
`br_dev` 网卡、`10.10.0.100/24`、网关 `10.10.0.254`、DNS `10.5.0.15` 和独立实例身份。
来宾根盘/分区/文件系统容量与首轮相同，根文件系统自动增长至约 125.8 GiB；cloud-init 完成、
QGA 正常、实例身份重新初始化，模板 9000 不变。DNS 来自实际上游 resolv.conf，
本地 resolver `127.0.0.53` 单独记录。

两轮常规清理的 PVE DELETE 原生任务停止并返回 `unexpected status`，分别只提供
`TrueNAS [INFO] : Ping` / `no content` 日志；后端原因未确定。不是删除后存储清单
5xx，不能用只读查询重试或改写结果消除。原始验收整体均保持 `unknown`，因此没有
取得一次常规清理也通过的原生模板验收结论。

rc.31 补齐当前 acceptance/v3 的恢复材料校验。新独立执行 `debian13-recover-rc31`
清除 rc.30 资源，`debian13-recover-rc31-02` 清除 rc.31 资源；均经新的只读 plan、
有限批准及本地互斥锁，确认原任务 inactive、完整资源归属后执行。两次恢复整体/清理通过，
VM500、两盘及专属 snippet 全部 absent、residuals 为空；不重放原执行或改写原未知结果。
最终独立只读观察再次确认 VM500/两盘不存在、模板不变。S3 本次上传的特定 VersionId 已删除，
发布的 local 暂存文件已清理；模板 9000 保留。

原始材料保留在 ONE 的受保护目录
`/home/clemon/iaas-acceptance/debian13-20261003-7bd92d5`：
成功产物在 `outputs/build-rc28/work/image-tasks/debian13-build-rc28/`，发布 record 在
`publish/generated/template-record.json`；首轮原始结果在 `accept/diagnostics/`，
独立只读观察在 `post-run-observation-rc28.json`。这些记录与后续新执行分开保留。
rc.30 原验收在 `accept-rc30/diagnostics/`，其删除任务的独立观察在
`native-delete-observation-rc30.json` / `native-delete-log-observation-rc30.json`。
最终验收在 `accept-rc31/diagnostics/`，两次恢复在 `recover-rc31/`、`recover-rc31-02/`；
最终只读观察在 `native-delete-observation-rc31.json`，凭据副本清理收据在 `credential-cleanup.json`。
保留产物与原始证据，只清除本次任务已定位的 17 份临时凭据/SSH 密钥副本，不撤销既有凭据。

## 调用方适配与结论边界

[代表性配置与正反例](../../../docs/examples/debian13-general-template/README.md)、[当前合同](../../../docs/contracts/image-publish-v1.md)及[操作说明](../../../docs/operations/image-publish.md)是适配入口。
离线 check 核验字段、关系和当前软件能力，不联网、不读取凭据、不写设施；基础盘实际容量在下载后、启动 Packer 前核验。
软件检查通过、限定真实模板验收、infra-ops 日常部署是三个独立结论。
infra-ops 自行负责正式清单、权限/凭据接线、计划审批、日常 apply 开放及部署后的来宾/业务验收。

离线完整克隆配置的 `check` 已在无网络容器中通过（`dev` 池、8 CPU/8 GiB/128 GiB）。真实现场使用专用验收池；尚无正式 `dev` 池日常部署或业务验收结论。后端 DELETE 失败需定位并用新的限定执行复验常规清理；在此之前保留独立恢复能力及失败关闭，IaaS 不接管宿主存储插件维修、权限或日常 apply 开放。
