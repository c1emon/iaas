# 实施与交付状态

## 软件验证

- 环境：macOS、项目 uv Python 3.12 环境；原生执行使用假 PVE API/guest、可控 UTC/monotonic，helper 使用本地临时文件系统。
- PVE 相关回归及 runtime dispatch：493 passed；随后新增/修正路径的合同、执行绑定、期限与 cleanup 定向复验：101 passed。
- helper 定向集成、普通上传回归及 launcher local/DinD 传输 fixtures 通过；Go launcher 全套测试通过，linux/amd64、darwin/arm64 launcher 与 SHA256SUMS 已本地构建（development 标识）。
- 改动 Python 文件 Pyright 无错误；JSON schema 与当前 v2 模型同步，OpenSpec strict 通过。

覆盖准入到期/相等、迟到阶段、持久化期间到期、工作截止转清理、逐项清理截止、原生/guest/helper 未知结果、远端锁后检查、UTC 后跳进入 cleanup 不延长预算、只读 observe 和新授权 retry。资源 unknown 与本次 facility_writes 独立；本地超时不构成取消或回滚。

## 发布状态与限制

runtime/launcher 新固定版本尚未发布，未完成的交付任务保持未勾选。交互式 gh 的 1Password 授权连续超时，尚不能推送、创建 PR 或触发正式 release；等待本机授权恢复。本机 Docker CLI 缺少 buildx，现有 runtime 构建脚本因此未能执行；没有用其他构建流程替代正式 release 校验。

恢复后使用既有 CI/release 流程，以实际发布产物确定新版本、manifest/platform digests、launcher checksums 及 v2 能力，再更新本记录。不覆盖历史版本。本地软件/传输 fixtures 和 launcher 构建不是实际 DinD daemon、真实 PVE、共享存储或生产资格证据；未执行现场设施写入。
