# ONE 真实复验（2026-10-04）

两轮复验（源码 `f3e9a57`、`3012664`）均 **overall passed**：
六项功能检查与 VM、卷、snippet 清理全部 passed，residuals 为空，stopping 为 null。
构建、发布及模板退役均成功；本轮资源与凭据副本已清理，原有 500/9000 保留。

## 覆盖与限制

- ONE 宿主 Docker 本地构建，实际经过 S3 传输、PVE 发布、完整克隆、128 GiB 扩容、首次启动、QGA、cloud-init、身份注入及源模板不变检查。
- 目标 `astra-pve` / cohe，池 `iaas-acceptance`，桥 `br_dev`；模板 9001、VM 501，8 CPU / 8 GiB。导入暂存 local，系统盘和 cloud-init 盘 memory；apt 使用 IPv4 镜像源。
- 两轮 DELETE 均一次成功，**未现场触发 5 秒／15 秒存储插件兜底**；重试分支仅有定向软件测试证据，不能证明插件根因已修复。
- 无故障注入、CI、DinD 或 OCI 发布；调用方准入材料与互斥由本地脚本提供，未覆盖 infra-ops 集成或生产资格。
- 首轮准备阶段曾因模板记录不匹配、构建参数/路径及容量缺测而拒绝或 unknown；原件保留，历史结果不提升。再次复验未遇到这些问题。

## 证据

ONE 根目录 `/home/clemon/iaas-test-oesd/`：

| 源码 | 测试材料 | 构建材料 |
| --- | --- | --- |
| `f3e9a57` | `retest-20261004-f3e9a57/` | `b3/` |
| `3012664` | `retest2-3012664/` | `b4/` |

各测试目录保留 `test-summary.json`、`outputs/accept-normal-03/diagnostics/execution/`、
发布/退役材料，以及 `facility-final-observation.json`、`s3-cleanup.json`、`host-cleanup.json`。
构建材料保留原生 artifact/build-result；临时磁盘已删除。首次失败与恢复见 [原验收记录](acceptance.md)。
