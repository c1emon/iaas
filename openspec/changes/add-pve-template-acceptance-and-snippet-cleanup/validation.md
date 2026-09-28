# 软件交付验证

2026-09-29，macOS arm64，独立 uv 项目环境；实施分支
`feat/pve-template-acceptance-and-snippet-cleanup`。

- 定向 Python：181 passed。覆盖合同/shared fixtures、真实 publisher record 和部署材料 producer、fake HTTPS/guest 验收与 finally 清理、未知 native 任务、总磁盘上限（含 cloud-init）、原执行绑定/观察、snippet 来源/引用/摘要/权限/部分完成/retry，以及现有发布和删除回归。
- Go launcher：`go test ./...` 与本机 `go build` 通过。local/DinD 文件传输、能力版本拒绝和收集失败为软件 fixture；未运行真实 Docker/DinD daemon。
- 改动 Python/helper 的 Ruff、四份 schema 导出一致性及正例 schema 校验、bootstrap Ansible syntax-check、OpenSpec strict validate 通过。
- 提交前 GitNexus detect-changes 完整返回已观察变更（无 partial/truncated）。新增生命周期和共享观察入口有 HIGH/CRITICAL 图风险；已用实际调用点与定向测试核对。增量索引曾扩展到无关流程，强制重建后范围收敛；全仓流程发现仍有预算限制，不能据图断言不存在其他调用。

交付合同：[pve-acceptance-cleanup-v1](../../../../docs/contracts/pve-acceptance-cleanup-v1.md)。
所有 task 按软件交付边界完成。没有执行真实 PVE 创建/删除、helper 安装、发布、PR、合并或 infra-ops 修改。
现场资格仍需单独指定节点、VMID、存储及创建/删除授权窗口。当前 cleanup helper
要求 quorate pmxcfs 的完整集群视图，无法证明范围时保留文件；相同文件名跨无关存储的引用会保守阻止删除。
