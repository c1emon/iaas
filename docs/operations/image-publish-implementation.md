# 镜像构建与 PVE 发布验证摘要

通用接口与操作规则见 [镜像发布手册](image-publish.md)、[PVE 手册](03-pve.md)和
[合同](../../openspec/changes/separate-image-build-and-pve-publish/contracts/image-publish-v1.md)。
本站执行器、制品和 CI 配置见 infra-ops 的
[接入说明](../../../infra-ops/docs/operations/image-build-pve-publish.md)。

| 测试项目 | 环境 | 最终结果 |
| --- | --- | --- |
| 镜像构建与独立测试 | 2026-09-23，ONE 的 Linux amd64 Docker/KVM | Debian 13 qcow2 构建通过；一次性来宾的首次启动、cloud-init、guest-agent 通过，原始磁盘未改变，任务清理无残留。 |
| 模板发布及 VM 生命周期 | 2026-09-23，cohe PVE 9.2，串行执行 | 模板 VMID 9003 经 HTTPS 上传、导入、配置并转为模板；临时 VMID 799 完成创建、配置核对和删除，模板随后退役。VM 799 未启动，故无 PVE 来宾验收结论。 |
| 固定版本的 CI 构建交接 | 2026-09-24，ONE 上的 `infra-ops-image` Forgejo Runner | `v0.1.0-rc.13` 的 image-builder 完成构建、独立来宾测试并上传不可变制品 `astra-debian13-20260924-004`；必需检查通过，测试清理无残留。 |
| CI 模板发布与退役 | 2026-09-24，cohe HTTPS API | 使用上述制品发布测试模板 VMID 9002，随后按独立退役请求删除；未进行模板克隆的来宾或业务验收。 |

2026-09-24 的清理复查确认测试 VMID 799、9002、9003 均不存在；旧 `pve-live`
对象存储前缀、临时目录存储及测试授权已清理。ONE 的两套 Runner 和数据卷是保留的基础设施。
`astra-debian13-20260924-004` 制品仍留在 S3，因为 infra-ops 中已提交的发布请求引用它；
清理该制品前须同步处理引用和保留策略。以上结论仅覆盖所列任务和环境。

## 后续操作需保留的注意事项

- VM 799 的原执行结果因 PVE 省略默认 `bios` 字段而报告验证失败；修复后的只读复核通过，原结果未被改写，调用方按原执行人工核清。当前配置读回不能补造历史执行成功。
- PVE 模板的配置验证不等于来宾启动或业务验收。ONE 上的一次性来宾测试只证明镜像构建/测试路径；模板推广仍由调用方独立决定。
- 通过 PVE HTTPS API 发布可避开 TrueNAS 插件写入 stdout 对 `pvesh` JSON 解析的干扰；本次未修改 TrueNAS 插件。旧模板 helper 曾将共享 `/run/lock` 改成 `0700` 并影响 pveproxy，已退役；迁移和恢复边界见[迁移说明](image-publish-migration.md)。
- 镜像制品上传后的状态是 `uploaded/unverified`：发布端仍须按固定对象身份下载并核对大小和 SHA-256。发布失败或响应未知时保留原执行与 pending，不以当前模板存在推断原执行成功。
- [OpenSpec 任务 5.4](../../openspec/changes/separate-image-build-and-pve-publish/tasks.md)中的“同一制品再次发布而不重建”尚无现场验收；本次 CI 的新制品发布不能替代它。
