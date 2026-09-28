# Tasks

实施分支：`feat/support-pve-vm-private-ca`。以下按已完成的软件实现与验证勾选；现场接入不在本次完成范围内。

## 1. 输入与 API 信任

- [x] 1.1 实施前检查工作树并按仓库规则确认实现分支；对拟修改符号重新执行 GitNexus impact，记录实际调用范围后再改代码。
- [x] 1.2 将 `files.api_ca` 接入 VM 在线操作的选择、路径映射及运行时配置，在通用文件准备层进行 CA 内容校验前处理 insecure；补充发现／传输、insecure 加空 CA 不提前失败与离线不读取测试，并在调用方示例中说明文件归属及可选性。
- [x] 1.3 统一 urllib 与 proxmoxer 的 TLS 选择和安全错误；以本地 HTTPS 分组测试覆盖有效 CA、错误 CA、空／无效 PEM 不被公共根掩盖、证书过期／未生效、SAN 不匹配、系统默认信任，以及 insecure 加无效 CA 内容仍跳过校验；检查 runtime／launcher 安全诊断出口，更新 TLS 行为说明。

## 2. Provider 与原计划材料

- [x] 2.1 为锁定的 Linux runtime/provider 接入任务级合并 CA bundle，保持公共根和显式 backend/AWS CA 选择；用真实 provider 对本地 TLS 服务的代表性握手验证严格模式与 insecure，补充环境传递和任务间不泄漏测试，说明同一 OpenTofu 进程内默认根可能扩展的边界。
- [x] 2.2 在 plan 首次使用前冻结有效私有 CA，扩展现有伴随文件、相对路径与摘要校验；让 apply／verify 恢复原 CA，测试源路径消失、当前 CA 不覆盖、保存材料缺失／变化／越界在副作用前失败，以及无 CA／insecure 不新增 CA 要求，并更新 saved-plan 文档。
- [x] 2.3 补齐 launcher 对 CA 伴随材料的传输与保留；复用本地 Docker／DinD 传输测试和跨目录原计划执行测试，确认 apply 与独立 verify 都能获得 CA，更新跨 Runner 示例。

## 3. 集成与交付

- [x] 3.1 运行受影响 Python 测试（通过 `uv run`）、launcher Go 测试、相应静态校验和 OpenSpec strict validate；提交前运行 GitNexus detect_changes，结合实际 diff 确认范围，简要记录结果与软件测试边界。
- [x] 3.2 交付 infra-ops 接入说明：runtime 选择、`files.api_ca`、原计划伴随材料保留及 insecure 优先级；核对示例与实际合同一致，不将软件测试表述为真实 Runner／PVE 验收。

默认工作量 M（2–4 天），限当前能力的 A/B 级实现与验证。真实站点接入保留到 infra-ops 使用目标 runtime 时确认；若发现必须扩大平台支持或真实环境验收范围，先重新评估，不自动追加资格矩阵、发布演练或证据系统。

## 验证结果

- Python 定向回归：输入／API 95 项、saved-plan／provider／runtime 82 项，全部通过；insecure 场景的两条 urllib3 警告为预期。
- Launcher：`go test ./...` 通过，覆盖 local／DinD、apply／verify 的 trust 传输、输出导出及 retained 存储保留。
- 本地 Linux arm64 实际 OpenTofu 1.12.6／锁定 provider 0.111.1：严格无 CA 拒绝、私有 CA 成功、后续无 CA 拒绝、insecure 加无效 CA 成功。
- Pyright、改动范围 Ruff、4 项 import-linter 合同及 OpenSpec strict validate 通过。
- 修改前执行 GitNexus impact；API 共享调用及 TLS 错误分类为 HIGH／CRITICAL，saved-plan 准入和 provider 环境为 HIGH，重点回归 read／plan／apply／verify。各阶段提交前执行 detect_changes，结果无 partial／truncated，结合实际 diff 核对范围；图报告 critical 不等同于真实环境故障或验收结果。

后续本地实测：macOS Python 两条 API 路径通过，原生 provider 的正确 CA 场景受已确认平台限制影响，按用户要求记录而不强行通过；本机 Docker Linux 连接真实 PVE 的 urllib、proxmoxer、provider 三类客户端各执行正确 CA、无 CA、错误 CA，共 9/9 场景通过。测试仅只读，容器及临时材料已清理。

本次未发布镜像，未执行 ONE Runner、真实 VM 生命周期或跨 Runner saved-plan 验收。接入方式见
[运行时操作说明](../../../../docs/operations/06-oci-runtime.md#pve-vm-private-ca-and-saved-plans)，
实际测试环境与复验命令见 [开发验证](../../../../docs/development-validation.md#pve-vm-private-ca)。
