# Runtime 验证范围与特殊失败边界

本文汇总 2026-09-11 Runtime 适配及后续修正的历史验证范围，不代表当前发布或目标环境状态。
使用方法见[启动器指南](runtime-launcher.md)与[环境配置](runtime-configuration.md)。
常规测试结果以对应提交的测试报告和 CI 为准。

## 验证范围

| 环境 | 已覆盖范围 | 限制 |
| --- | --- | --- |
| Apple Silicon 上模拟 AMD64 | 本地 Docker、独立 DinD 文件传输、临时 Forgejo 作业及合成 OpenTofu 计划 | 不代表原生 AMD64 硬件或共享 Forgejo 环境 |
| Apple Silicon 原生 ARM64 | 镜像构建、离线生成、provider 初始化与校验、本地启动器结果回收 | 未重做 ARM64 DinD、Forgejo 或 S3 故障恢复 |
| 临时 MinIO、合成资源 | state 读写、锁冲突、过期计划拒绝、写回失败后的恢复文件保留 | 不代表真实设施或调用方 S3 服务资格 |
| 本地临时 Registry | 双架构发布、重复发布和匿名 digest 拉取 | 不代表 GitHub Release 或 GHCR 发布已完成 |

上述验证没有执行真实 PVE、K3s、OPNsense 或交换机变更。发布状态以所选版本的
Release 结果为准；镜像架构支持见[启动器指南](runtime-launcher.md#native-arm64-builds)。

## 需要保留的特殊结论

- DinD 的 daemon 不必拥有客户端路径，输入需显式传输，不能依赖客户端目录挂载。
- S3 写回失败曾在临时 Forgejo 环境中实际触发；结果回收失败时保留任务卷，
  确认受保护恢复副本可读后才清理。恢复步骤见[保存计划与恢复](runtime-launcher.md#saved-apply-and-recovery)。
- 远程与本地 state 同时写入失败、原始流捕获失败等分支由软件测试覆盖，
  不应描述为真实磁盘耗尽实验。原始输出可能含完整 state，必须受保护捕获。
- 原生 state 锁不覆盖前置 SSH 上传；过期计划被拒绝时，snippets 可能已经写入。
  完整变更仍须由调用方串行安排，失败不承诺自动回滚。
- 保存计划缺少架构字段或配套文件清单时须重新准备，不从当前配置重建配套输入。
  详见[保存计划配置](runtime-configuration.md)。
- Docker containerd manifest 身份与经典 image config ID 不可混用；前者经本地实际
  发布验证，后者由软件测试覆盖。重试发布须复用原产物，见[发布规则](runtime-launcher.md#native-arm64-builds)。
