# PVE 验收与独立 snippet 清理共用样例

本目录是 **synthetic contract fixtures**，不代表 PVE 现场验收或可直接执行的授权。域名、UUID、摘要和证据路径均为示例，引用文件并未提供。真实请求须使用原发布/部署材料、准确摘要和独立 execution admission。

`cases.json` 是 IaaS 和 infra-ops 共用入口，列出每个 JSON 的 kind 和预期接受/拒绝；IaaS 的 `tests/python/test_pve_acceptance_contracts.py` 直接加载这份清单。文件名 `reject-*` 表示合同拒绝用例。结果成功样例也只是合同样例。

- `acceptance-request.json`：固定 publication record、临时 VM、注入 hostname、专用 snippet storage/SSH 目标、六项检查和三个有限期限。
- `cleanup-deployment-request.json`：原已批准删除计划、执行 admission、删除与 state 写回引用。
- `cleanup-acceptance-request.json`：原验收 request/journal、确认的临时 VM 删除与专属 snippet 所有权引用，无 plan/state。
- `cleanup-retry-request.json`：新执行使用原清单及前次 request/journal 引用。首次清理的 `retry_of` 和 `retry_materials` 必须同时为 null。
- `acceptance-result.json` / `cleanup-result.json`：允许公开的身份、检查/清理状态及完整性结论，不含 hostname、cloud-init 内容或 guest 输出。

对应 schema 在 `automation/schemas/pve-acceptance/v2/`。JSON schema 检查结构和 origin/retry 互斥分支；Python 校验进一步核对身份、期限和 overall 逻辑。实际 mutation 还须加载原证据，检查摘要、授权、原任务终止、完整引用范围和互斥；通过 schema 不等于获得执行授权。

使用既有 canonical JSON（键排序、紧凑分隔符、UTF-8、拒绝浮点及重复 key）计算 `sha256:` request digest。`options.execution_mode` 位于 environment，不属于固定请求。`EvidenceRef.sha256` 是无前缀的文件 SHA-256，路径相对于只读 evidence root；禁止绝对路径、逃逸及符号链接。

公共 `reason_code` 使用短小 snake_case，不能拼接异常、路径、guest 输出或秘密。固定检查 ID 为 `full_clone`、`disk_boot`、`guest_agent`、`cloud_init`、`injected_hostname`、`source_unchanged`。检查 `not_attempted` 表示因前序已知阻断未执行，不能用于已尝试但结果未知的检查。

独立 snippet 清理的 `ssh.host/user/port` 是固定请求的一部分，纳入 request digest 与 admission。使用非 root helper 账户；SSH 私钥及 known_hosts 仍由既有受保护文件通道提供，不内嵌请求。修改连接目标必须创建新的经批准请求，补执行不得换目标。

模板验收 start 同时映射 `files.ssh_key`、`files.known_hosts`；`cloud_init.ssh` 绑定受限 helper 账户。上传 helper 需支持 `--create-only`，删除 helper 需按 bootstrap playbook 安装。原模板 `ciuser` 通过专用 user-data 的 `users` 列表表达，验收不注入登录凭据，也不运行软件包更新。
