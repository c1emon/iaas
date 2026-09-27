# PVE VM 调用方私有 CA 支持

## Why

模板工作流已有 `files.api_ca` 入口，但 VM 在线检查、API 读取与核验、OpenTofu provider 尚未贯通该信任文件。由 infra-ops 提供的私有 CA 需要随原计划交付，避免计划和执行使用不同的信任材料或依赖原 Runner 路径。

## What Changes

- 将可选 `files.api_ca` 扩展到 PVE VM 在线操作，复用现有文件发现、传输和任务隔离机制，不将站点 CA 写入通用镜像。
- 严格模式下，各 PVE API 客户端和 OpenTofu provider 使用系统公共 CA 加调用方私有 CA；证书链、有效期和 IP／域名匹配失败均明确失败，不自动降级。
- 保留 `pve.insecure: true` 的优先级：即使提供 CA，仍跳过服务端证书校验，不因未使用的 CA 内容无效而失败。
- 将严格模式下实际使用的私有 CA 纳入现有 saved-plan 伴随材料及一致性检查，供其他 Runner 的 apply 和独立 verify 恢复使用。

## Capabilities

### New Capabilities

无。扩展现有能力，不新增证书管理子系统。

### Modified Capabilities

- `runtime-launcher`: VM 在线操作接收与传递可选 CA，保持操作隔离和本地 Docker／DinD 一致语义。
- `pve-api-runtime-adapters`: 统一预检查、健康检查、读取及结果核验的私有 CA、默认信任和 insecure 语义。
- `runtime-saved-plan-execution`: provider 使用相同信任，私有 CA 随原计划保存、校验并恢复。

## Impact

实现涉及 `src/iaas/runtime_execution/`、`src/iaas/pve_inventory/pve_api/`、预检查 HTTP adapter、`automation/launcher/` 及对应测试、示例和操作文档。复用 `PVE_API_CA` 内部约定，不改变调用方凭据、S3 backend 或部署授权职责。

预计 M（2–4 个工作日，含方案、实现和软件验证）。不以真实 PVE 或完整 Runner 发布演练作为本次软件完成条件；现场接入由 infra-ops 后续安排。

## Non-goals and delivery scope

本次只交付 OpenSpec change，等待后续实施授权。不管理证书签发、续期、吊销服务或 PVE 集群 CA 替换，不改变模板发布合同，不新增调度、审批、签名链或通用信任框架。验收采用必要正反例和代表性执行路径，不建立逐 VM／节点／证书的穷举矩阵。
