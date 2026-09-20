# Runtime 适配需求索引

原适配需求已纳入 [OpenSpec 归档](../openspec/changes/archive/2026-09-11-adapt-runtime-config-and-local-execution/proposal.md)。
本文保留原链接入口，不再重复维护需求编号、验收矩阵和实施清单。

## 当前使用文档

| 内容 | 文档 |
| --- | --- |
| 环境入口、事实引用、场景、路径和保存计划 | [环境配置](runtime-configuration.md) |
| 安装、版本选择、本地 Docker / DinD、凭据与失败恢复 | [启动器指南](runtime-launcher.md) |
| 镜像接口、构建和发布 | [OCI runtime](operations/06-oci-runtime.md) |
| 历史验证范围及特殊失败结论 | [验证边界](runtime-adaptation-validation.md) |
| 并发保护等后置事项 | [路线图](roadmap.md#deferred-pve-concurrency-protection-beyond-serial-execution) |

IaaS 维护通用配置契约与运行时。调用方维护真实环境、版本选择、凭据、S3 backend、
受保护计划和恢复材料，并负责完整变更流程的串行安排与部署授权。
