# 分离镜像构建与 PVE 模板发布

## Why

当前节点 worker 将 Debian 镜像加工、PVE 对象创建及清理放在一次远端任务中，镜像不能独立交付，构建还要求 PVE 宿主机安装 libguestfs。将已有加工能力提取为可由本地或 CI 调用的工具，再独立发布镜像，能够复用已有实现并收紧宿主机与凭据边界。

## What Changes

- 提供通用 `image` 能力：直接build/test/clean，以Packer QEMU构建、复用定制和libguestfs清理，支持独立测试既有镜像，输出自包含qcow2、SHA-256和真实结果；不为本地可重建任务强制plan/apply。
- 将 `pve-template` 改为消费已构建镜像的 HTTPS 发布能力：预检查、传输校验、导入、配置、转模板、验证、定向清理及退役。
- 将镜像加工移出PVE节点，发布不要求节点SSH或空间helper；只保留独立snippet能力所需helper，不保留第二套构建/发布写入路径。
- iaas 定义 [权威交接合同](contracts/image-publish-v1.md)；infra-ops 提供站点配置、执行器/CI、凭据、S3 上传与保留、推广及互斥。对应 [infra-ops change](../../../../infra-ops/openspec/changes/integrate-image-build-and-pve-publish/proposal.md) 同期规划、独立实施。
- **BREAKING**：停止接受旧的 template `action=build` 及加工参数；升级模板 preview/result/record 版本，VM消费方直接采用新record，不提供旧schema适配层。旧材料仅保留原始文件供人工调查，迁移后不得执行或隐式重建。
- 共享launcher分发、隔离与结果规则：image直接工具操作，PVE发布/清理/退役仍plan/apply；移除重复整盘回读与JSON字节门禁，已验证模板的已知静止暂存残留独立跟踪，不阻断发布。

## Capabilities

### New Capabilities

- `image-build-tool`: 独立镜像构建、定制、检查、最终清理与本地任务生命周期。
- `image-artifact-contract`: 自包含镜像产物和无凭据、可验证的跨仓交接。

### Modified Capabilities

- `pve-template-lifecycle`: 从节点构建改为外部 HTTPS 发布，保留身份关联、当前准入、可查询结果与归属感知清理。此能力由在途 `adapt-pve-ci-lifecycle` 引入；必须先归档其 delta，再应用本 change 的替代 delta。
- `pve-automation-foundation`: Debian 镜像与模板发布分离，禁止原地 force 替换。
- `runtime-launcher`: 增加 image 执行环境能力，升级 pve-template 协议，隔离各阶段输入及凭据。
- `runtime-saved-plan-execution`: VM克隆引用直接使用新模板记录合同，拒绝旧记录和计划输入；不改变原生OpenTofu执行/state职责。

## Impact

后续涉及 `automation/pve-node/bin/`、`automation/packer/`、`automation/src/iaas_automation/pve_template/`、runtime_execution、launcher、镜像构建资产、安装/卸载 playbook、生成器和操作文档。VM 原生 plan/state 与 OPNsense 候选/激活语义保持独立。

## Non-goals and delivery scope

本次只建立、联合复核并校验双仓 proposal/design/specs/tasks，不实施代码、不提交现场变更、不部署 CI 或执行器。未来实现首期覆盖 Debian 13 amd64、单系统盘 qcow2 与串行构建；不预建多云插件框架、调度服务、签名链、全局模板注册表、自动 GC 或全发行版矩阵。
