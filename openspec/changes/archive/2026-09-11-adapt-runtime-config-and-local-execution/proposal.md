## Why

调用方目前需要按运行时内部目录组织配置并手写容器命令，本地与 Forgejo DinD 的路径、输出和版本选择容易分叉。已确认的需求要求统一配置入口、独立组件操作、调用方管理的 S3 state，以及可保存并应用指定 OpenTofu 计划的完整失败处理。

需求依据：[IaaS Runtime 配置与本地执行适配需求清单](../../../../docs/iaas-runtime-adaptation-requirements.md)。已在实现分支完成代码及本地合成验收；范围与实际结果见[验收记录](../../../../docs/runtime-adaptation-validation.md)。

## What Changes

- 增加版本化环境入口、有限事实引用、显式场景及组件选择；将配置编译为现有组件输入，不引入第二套领域模型。
- 提供轻量启动器及相同的容器内操作接口，覆盖本地 Docker、Forgejo DinD、路径映射、退出/取消、文件权限与输出回收。
- 由调用方集中选择镜像版本和平台；检查配置格式、启动器接口与镜像兼容性。支持 Linux amd64/arm64 镜像构建及 Apple Silicon 原生 arm64 或显式 amd64 模拟；保存计划绑定运行架构，跨架构或缺少架构字段时需重新准备。
- Release 串行构建并验证两个架构，复用已测试产物发布架构标签和同一版本的多架构 manifest，再分别验证匿名消费。已有标签不覆盖，同一产物可续发；历史单架构版本保持不变。
- 保持纯检查/生成断网、无凭据；依赖准备、设备诊断、在线计划和变更分别声明能力及副作用。
- 为新入口的 state 操作接入调用方提供的 S3 backend 和原生锁；保留写回失败的恢复 state，覆盖本地恢复文件也写入失败时的受保护紧急输出，禁止自动迁移、回退本地 backend 或重试变更。
- 增加受保护的原生计划及配套输入保存、传递和应用，以配套 manifest 中的原生 plan SHA256 防止误混用；保留直接执行入口的明确语义，不将其作为指定计划失败后的回退。
- 复用调用方单任务串行 CI 约定；明确上传先于 OpenTofu 过期检查，失败可能已经覆盖 snippets。新增跨入口执行锁和不可变 snippets 保持延期。
- 保留现有显式目录/文件入口及其领域校验；新入口不自动猜测旧格式，不自动改写调用方配置或 state。

## Capabilities

### New Capabilities

- `runtime-environment-config`: 版本化环境入口、事实引用、场景与依赖选择、路径保护及明确迁移。
- `runtime-launcher`: 本地/DinD 统一启动、操作分级、版本兼容、权限、任务与输出生命周期。
- `runtime-saved-plan-execution`: 原生计划与配套输入的保存和应用、授权绑定、串行执行及失败边界。

### Modified Capabilities

- `oci-runtime-delivery`: 发布启动器及兼容元数据，支持 amd64/arm64 同标签镜像发布，明确平台能力和分组验收，保持运行镜像内容边界。
- `pve-state-and-secret-operations`: 调用方 S3 接入、按操作注入、恢复 state 的保留及 runbook 责任。
- `pve-automation-foundation`: 区分直接执行与保存计划的当前输入/顺序契约，更新 state 文档约定。

## Impact

实现新增 `automation/launcher/`、Python 配置/执行适配、容器协议、保存计划及恢复路径，并更新发布工作流、测试与操作手册。复用现有 paths/cloud-init/Ansible 领域能力；原 Make 入口、VM 资源地址、主机 helper 权限边界和基础设施所有权保持原有契约。

本轮已获实现分支和本地 Docker 测试授权，只使用任务专属 Colima、Forgejo/DinD、MinIO 与临时本地 Registry。原生 arm64 镜像构建及代表性运行、两个架构的本地多架构发布验证已完成。没有修改调用方真实配置或设施，没有向 GHCR 发布镜像或创建正式 Release、启动器发布。共享环境、真实设施及 native amd64 硬件资格不由这些本地结果替代；原有 DinD/S3 验证不扩展为 arm64 验收。
