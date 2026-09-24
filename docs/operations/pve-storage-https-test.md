# PVE 存储 HTTPS 适配测试

本轮先验证查询通道和预检查，不创建模板、VM 或临时存储，不修改 TrueNAS 插件。
软件替身测试不等于实机通过。此前执行的旧 plan/admission 不得重放。

## 1. 离线回归

在仓库根目录执行：

```bash
uv run pytest -q tests/python/test_pve_node_storage_https.py \
  tests/python/test_pve_node_template_helper.py \
  tests/python/test_pve_template_lifecycle.py \
  tests/python/test_pve_template_admission.py
openspec validate adapt-pve-ci-lifecycle --strict
```

覆盖本地真实 TLS 服务、服务端 stdout 日志不进入 HTTP 正文、固定 loopback/GET 路径、
本机证书匹配、认证失败、HTTP 错误/重定向、非 JSON/超限响应，以及 worker 获锁后重新检查。
目录卷构建使用离线替身；不连接 PVE 或 TrueNAS。

## 2. 节点只读对照

使用既有可信 SSH host key 和 root 管理身份。保持原插件 `Stdout` 配置；
不为了本次对照调整插件或 pveproxy。先确认本轮实际节点/PVE 版本及维护窗口。

新探针可直接通过 stdin 执行，不必先安装到节点：

```bash
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes root@<pve-host> \
  'python3 - <local-node-name> <storage-id>' < automation/pve-node/bin/iaas-pve-storage-status
```

预期 stdout 只有合法 JSON，包含 `type/content/enabled/active/avail`；不输出 ticket、
插件日志或其他响应字段。选择已存在的普通目录存储和插件存储作代表性对照，
当前能力必须重新读取；只查询，不创建资源。
本探针每次在内存中生成节点 root ticket，校验 TLS 后才发送到 loopback；没有控制端 token 注入。

如需对照旧 CLI，将 `pvesh get /nodes/<node>/storage --output-format json` 的 stdout/stderr
分别捕获到调用方权限 0600 的临时文件，仅报告退出码和 JSON 是否可解析。
不要直接打印原始响应；插件日志可能包含敏感内容。对照完成后删除这两个临时文件。
成功标准是原插件保持不变时 HTTPS 可解析，不要求 CLI 每次都恰好产生噪声。

证书/认证错误、连接超时、HTTP 非 200、字段缺失或格式错误即停止；不使用 `-k`、
不关闭证书检查、不过滤日志拼凑 JSON、不回退到 pvesh 存储查询。

## 3. 统一入口预检查

只读对照通过后，在已授权的节点部署窗口备份并一起安装三个 root-owned 入口：
`iaas-pve-template`、`iaas-pve-template-worker`、`iaas-pve-storage-status`。
沿用 [安装步骤](03-pve.md#33-pve-节点自动化账户与模板-helper)，不新增 sudoers 权限。
新探针是内部 root 工具，不能单独授予 pve-ops 任意执行权限。

调用方重新解析临时 SSH key/trust，使用本轮新输出目录，通过统一 `pve-template plan/check`
路径验证不支持 images 的现有存储被拒绝。若需成功计划，必须选取当前支持 images、启用、
活动且空间充足的存储，以及当前确认空闲的模板 VMID；只执行 plan，不执行 apply。
检查错误发生在下载/创建前，确认没有新 worker 或 VM，随后删除临时 SSH 私钥。

worker 内部重查已由离线集成回归覆盖。若后续需要新的实机构建验收，再使用新计划与新
execution ID，在新的有效窗口内按单模板、单 VM、串行范围执行并清理；不把本轮只读结果
表述为模板构建、首次 state 采集或 guest 验证通过。
