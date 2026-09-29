# 软件交付验证

2026-09-29，macOS arm64，独立 uv 项目环境；实施分支
`feat/pve-template-acceptance-and-snippet-cleanup`。

- 定向 Python：181 passed。覆盖合同/shared fixtures、真实 publisher record 和部署材料 producer、fake HTTPS/guest 验收与 finally 清理、未知 native 任务、总磁盘上限（含 cloud-init）、原执行绑定/观察、snippet 来源/引用/摘要/权限/部分完成/retry，以及现有发布和删除回归。
- Go launcher：`go test ./...` 与本机 `go build` 通过。local/DinD 文件传输、能力版本拒绝和收集失败为软件 fixture；未运行真实 Docker/DinD daemon。
- 改动 Python/helper 的 Ruff、四份 schema 导出一致性及正例 schema 校验、bootstrap Ansible syntax-check、OpenSpec strict validate 通过。
- 提交前 GitNexus detect-changes 完整返回已观察变更（无 partial/truncated）。新增生命周期和共享观察入口有 HIGH/CRITICAL 图风险；已用实际调用点与定向测试核对。增量索引曾扩展到无关流程，强制重建后范围收敛；全仓流程发现仍有预算限制，不能据图断言不存在其他调用。

交付合同：[pve-acceptance-cleanup-v1](../../../../docs/contracts/pve-acceptance-cleanup-v1.md)。
初次交付按软件边界完成；后续已在用户授权窗口完成下述现场复验。未发布运行时镜像、创建 PR、合并或修改 infra-ops 源码。当前 cleanup helper
要求 quorate pmxcfs 的完整集群视图，无法证明范围时保留文件；相同文件名跨无关存储的引用会保守阻止删除。


## 两项现场问题修正后的复验

2026-09-29，ONE 独立目录运行当前源码候选，连接 cohe；模板 9004、临时 VM 9005，memory 磁盘与 images snippets。依赖基础层的 uv.lock/pyproject.toml 与仓库一致；这不是最终发布 Dockerfile 的完整重建资格。

- 模板发布、六项最小验收、源模板未变和 VM/卷/验收 snippet 自动清理全部通过。cloud-init 返回 done、无 recoverable_errors，模板声明的 ciuser 保留并通过 users 列表注入。
- 从新模板独立创建关机 VM、UUID 写入 state 和 API 核验通过；重复计划 no-op。移除 inventory 后删除通过，删除计划 UUID 与创建结果一致；独立 snippet-cleanup 入口删除两份文件，无手工补救。
- 无凭证、禁网 observe 精确复现验收结果。9004/9005、所属卷、三份 snippets、临时 ACL/helper、ONE 目录与候选镜像均清理；原上传 helper 恢复，独立 state 留空，serial 12。
- Python 全套 1566 passed、2 skipped。新增合同/失败路径、独占上传和真实 deployment target 形状覆盖通过。

测试 root 显式固定 API endpoint 与 insecure=false：OpenTofu 1.12.6 将环境变量注入的 bool 在计划 JSON 中呈现为字符串，现有 provider 合同会拒绝；本次未扩展修复该独立问题。旧 state 缺 UUID 的历史材料仍不能用于补造清理证据；已有 VM 应审查首次应用新模块的 SMBIOS 变更。
