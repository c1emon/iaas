# 镜像交付（2026-10-04）

[PR #41](https://github.com/c1emon/iaas/pull/41) 已合并至 main：`6027e296b656e8e87e953b2976a3ab85cf7f15dc`。
本地与远端实现分支已删除。

[Release v0.1.0-rc.32](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.32) 的
[OCI workflow](https://github.com/c1emon/iaas/actions/runs/37176189840) 七项作业全部成功，
覆盖双架构 runtime 构建、amd64 image-builder、launcher 资产、发布及双架构匿名消费。
GHCR 匿名读取确认版本、源码 revision 与下列架构一致；消费时固定 digest。

| 镜像 | 平台 |
| --- | --- |
| `ghcr.io/c1emon/iaas-runtime@sha256:af5a7fe9ecce1e8f566ddea3b8bd03d990936c87517b907d057f23bdbc974203` | linux/amd64, linux/arm64 |
| `ghcr.io/c1emon/iaas-image-builder@sha256:16b7974911eb3193298187c5026385593ede7a85888204010907bd85bb715417` | linux/amd64 |

此为软件镜像交付；真实设施覆盖及未现场触发的 DELETE 兜底限制见 [验收摘要](acceptance-retest.md)。
