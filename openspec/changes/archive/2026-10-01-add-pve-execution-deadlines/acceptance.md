# 实施与交付状态

## 软件验证

- 环境：macOS、项目 uv Python 3.12 环境；原生执行使用假 PVE API/guest、可控 UTC/monotonic，helper 使用本地临时文件系统。
- PVE 相关回归及 runtime dispatch：493 passed；随后新增/修正路径的合同、执行绑定、期限与 cleanup 定向复验：101 passed。
- helper 定向集成、普通上传回归及 launcher local/DinD 传输 fixtures 通过；Go launcher 全套测试通过，linux/amd64、darwin/arm64 launcher 与 SHA256SUMS 已本地构建（development 标识）。
- 改动 Python 文件 Pyright 无错误；JSON schema 与当前 v2 模型同步，OpenSpec strict 通过。

覆盖准入到期/相等、迟到阶段、持久化期间到期、工作截止转清理、逐项清理截止、原生/guest/helper 未知结果、远端锁后检查、UTC 后跳进入 cleanup 不延长预算、只读 observe 和新授权 retry。资源 unknown 与本次 facility_writes 独立；本地超时不构成取消或回滚。

## 固定版本交付

[v0.1.0-rc.16](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.16) 固定到提交 `853873d172ae99266af040e2cd25ab4709b35656`。[PR offline-validation](https://github.com/c1emon/iaas/actions/runs/36681430052) 和[正式 oci-release](https://github.com/c1emon/iaas/actions/runs/36682646127) 全部成功。发布流程完成两个架构的构建、镜像检查、launcher 上传及干净匿名 digest 拉取/启动；amd64 仓库检查记录 Python `1890 passed, 4 skipped`，Pyright `0 errors`。

| 产物 | 固定摘要 |
| --- | --- |
| runtime manifest | `sha256:c180df3e1c25c2119b6de721e7d91d6b81fca95d157fdd9a4b0486b01590b238` |
| runtime linux/amd64 | `sha256:c5521ff4144d7bcd883e588d5deb5798f20ff7e45bc69ee344d0deb85c954c41` |
| runtime linux/arm64 | `sha256:c6dab87d11168f417380546af6342d6de30cca6223f68362ecfeeb4384d68178` |
| launcher iaas-linux-amd64 SHA256 | `246467cb7e45e33ac17cddf1d5cc5f19172597d325d50f8b82d4fda1fe99882a` |
| launcher iaas-darwin-arm64 SHA256 | `c1763171cb28da6269409a1ebf32562d147a687cd8acd7f2974e5dc180ec79d2` |

infra-ops 可固定消费 `ghcr.io/c1emon/iaas-runtime@sha256:c180df3e1c25c2119b6de721e7d91d6b81fca95d157fdd9a4b0486b01590b238`，并从该 release 下载平台 launcher 与 `SHA256SUMS`。两个 launcher 下载摘要均已核对，macOS ARM64 版本输出为 `iaas v0.1.0-rc.16`；本地按 manifest digest 启动 ARM64 镜像确认两个操作均声明 `absolute_deadlines: true`，对应 request/result 均为 v2，OCI 标签的源提交和版本与发布一致。

本机 Docker CLI 缺少 buildx，因此正式 runtime 构建证据来自上述 CI。未覆盖历史版本。本地软件/传输 fixtures 不是实际 DinD daemon、真实 PVE、共享存储或生产资格证据；本次发布和镜像消费检查也不构成设施验收，未执行现场设施写入。
