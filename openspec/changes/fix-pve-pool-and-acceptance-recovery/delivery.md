# 软件交付与现场边界

实施分支：`implement/fix-pve-pool-and-acceptance-recovery`。本 change 仅修改 IaaS。

当前合同：publication request v2、preview/result/record v3；acceptance request/result v3、preview v1；acceptance/recovery one-shot admission v2；recovery request/preview/result v1。新 start 不接受旧合同；rc.19 原验收 v2 仅供恢复读取。

节点需安装本版本 upload/delete helper 和 wrapper-only sudo 规则，并固定 SSH key/known_hosts。验收池权限继承的只读编译使用节点原生 PVE 权限模块；不写池或 ACL。普通 VM 创建恢复完整必要权限预检，未来入池后的权限无法证明时明确拒绝；publication 的预检保持原范围。已有 VM 的 pool 改为空值受 provider 0.111.1 限制，准入拒绝；新 VM 可不指定 pool。

后续适度工程调整（待发布 rc.21）：仅缺失关联的旧 guest-exec 历史未知可由新批准限定处置；preview 显示 administrator_decision，沿用现有批准，不重建 trace、不新增门禁。当前任务查询失败/异常、helper或旧恢复活动无法核清必须阻断；归属、引用与本次响应丢失保护保留；完整 helper 引用无需重复全局 API 可见性，旧结果允许部分/unknown 信息，历史恢复链不要求补齐。独立 snippet 清理不依赖无关旧任务终态。rc.20 发布产物仍是下述原源码，不包含本次调整。

调整验证：Python 全套 1802 passed、2 skipped；最后补充与调整后的定向回归 116 passed；Pyright 0 errors、Ruff、4/4 import contracts 和 OpenSpec strict 通过。无 launcher/Go/Tofu 修改，没有扩展到现场或发布复验。

软件验证：完整 Python 1792 passed、2 skipped；全项目 Pyright 0 errors、Ruff 通过、4 个 import contracts 保持；Go 全套通过；OpenTofu 模块 fmt 与锁定 provider fixture init/validate 通过；OpenSpec strict 通过。API/helper、local/DinD 传输均为软件 fixture，不能作为真实 PVE 或共享环境验收。

固定版本 [v0.1.0-rc.20](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.20) 已发布；源码 `904e92ef81256263b48ee4f2c5c539a0b0180ee1`。[release 工作流](https://github.com/c1emon/iaas/actions/runs/36862950966) 全部成功，两个平台各自 `make check` 为 2093 passed、4 skipped，并完成匿名 digest 拉取及 capabilities 平台调用。当前合同字段另由源码导出和 launcher 合同/分发测试验证。

| 产物 | 实际摘要 |
| --- | --- |
| runtime manifest | `sha256:4e2eb186b1d3123f6e3b492d117ecf81e2458e8de35f175fd9759de8e020b117` |
| linux/amd64 | `sha256:4aefdd7bc916fef6463ef36b7d52825b7b6e46d3a3dedcafc5884ef581beda81` |
| linux/arm64 | `sha256:09d3227e0b749327c1fcef4067265594159eda84dc8854eda3f105a49acc5dea` |
| iaas-darwin-arm64 SHA256 | `4337b83d709ec5ef18a526ec1ca32d53b22b3aff4558106b3d60f5e908923cd3` |
| iaas-linux-amd64 SHA256 | `52000c4b4f2314b78d97fe88c4d897fac8480e44ce55550855d6c31830d566d5` |

固定镜像为 `ghcr.io/c1emon/iaas-runtime@sha256:4e2eb186b1d3123f6e3b492d117ecf81e2458e8de35f175fd9759de8e020b117`。已读取 registry descriptor 核 manifest/platform 摘要；下载两个 launcher 并核 SHA256SUMS，macOS launcher `--version` 返回 `iaas v0.1.0-rc.20`。正式恢复输入与命令见 [操作说明](../../../docs/operations/pve-acceptance-recovery.md)。

task8.1 由 infra-ops 承接现场 plan、新限定批准与精确清理；IaaS 不执行现场操作，也不以该外部任务未完成阻断软件交付。原验收仍未通过，现场资源存在性尚未验证。缺失旧 guest-exec 关联可保留 unknown；当前任务/恢复活动无法核清则不得清理。

2026-10-02 审核修正（待发布）：恢复当前任务查询失败与异常状态的零写入阻断，历史 guest-exec 缺关联仍可限定处置；恢复普通 VM 全部必要权限预检。Python 全套 1808 passed、2 skipped；Pyright、Ruff、4/4 import contracts 与 OpenSpec strict 通过。
