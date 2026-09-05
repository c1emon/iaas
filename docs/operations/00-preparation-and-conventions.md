# 0. 准备与通用约定

本章在任何交换机、OPNsense、PVE、VM 或 K3s 操作之前执行。它定义控制机
材料、配置所有权、运行时凭据和证据规则；后续章节不重复这些通用约束。

## 0.1 准入材料

| 类别 | 必须准备 | 不得提交或输出 |
| --- | --- | --- |
| 控制机 | macOS/Linux、Git、`uv`、OpenTofu、Ansible 依赖、1Password CLI/会话、SSH agent。 | 私钥、SSH agent 导出、shell 历史中的密码。 |
| 仓库 | 干净工作树、已同步依赖、当前生成物、已审查的变更范围。 | `.venv`、provider 缓存、Ansible collection、临时导出。 |
| 网络设备 | 设备管理地址、可靠的本地或带外控制台路径、受限 API/SSH 凭据。 | OPNsense API secret、交换机密码、设备导出中的凭据。 |
| PVE/VM | PVE API 与 SSH 运行时环境、模板镜像 URL/校验值、PVE 存储和 bridge 事实、VM 用户公钥。 | OpenTofu state、cloud-init 用户密码、VM 私钥。 |
| K3s | 已审查的 intent、生成的 PVE inventory、完整节点 scope、受限权限的运行时密钥 JSON、镜像/Registry/代理可达性。 | server token、Registry 密码、TLS 私钥、运行时 JSON 内容。 |

运行以下离线准备命令；它们不联系内部设备，也不读取运行时凭据：

```bash
uv sync --locked --dev
make generate
make check
make secret-scan
```

`make generate` 会重建已提交的非敏感生成物；`make check` 只验证源、生成物、
测试、YAML、Python 类型、OpenTofu 形状、Ansible lint 和 OPNsense 期望状态。
它不是 PVE、OPNsense、交换机、VM 或 K3s 的运行证明。

需要执行 Ansible 章节时，先在 `automation/ansible/` 安装锁定 Python 依赖和
collection：

```bash
cd automation/ansible
uv sync
uv run ansible-galaxy collection install -r requirements.yml
```

本地 collection 未被 Ansible 自动发现时，按该次命令显式设置
`ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:$PWD/collections"`。这些
collection 是本地依赖，绝不提交到仓库。

## 0.2 配置与生成链

```text
环境 YAML / Ansible vars / runtime 模板
        │
        ├─ Python 校验与归一化
        ├─ OpenTofu、Packer、Ansible 输入
        └─ committed generated references
                │
                └─ 在线只读或显式变更操作
```

编辑顺序必须是：源配置 → 离线校验/生成 → 审查 diff → 在线只读确认 → 明确的
变更操作。不得反过来先手改 `environments/astra/generated/`、PVE 中的派生值或
来宾内角色托管文件。

## 0.3 命令安全等级

| 等级 | 典型命令 | 规则 |
| --- | --- | --- |
| 离线安全 | `make generate`、`make check`、`make secret-scan`、`make pve-check`、`make k3s-check` | 不依赖内部网络或运行时密钥；结果只证明本地源与合同。 |
| 在线只读 | `make pve-health`、`make pve-preflight`、`make pve-verify-guests`、`make k3s-preflight`、`make k3s-verify`、设备 readonly/export | 必须显式提供运行时上下文；保存结果并检查 `WARN`/`SKIP` 的含义。 |
| 变更操作 | PVE `plan/apply/destroy`、Packer、来宾 bootstrap、交换机 apply、OPNsense 管理 playbook、K3s deploy/snapshot/upgrade | 必须先满足该章节准入条件，并记录范围、操作者、恢复路径、实际命令和结果。 |

永远不要把在线操作加入 `make check`、云 CI 或无人值守命令链。`SKIP`、缺失
凭据或模拟 fixture 不是成功证据。

## 0.4 运行时凭据与文件权限

| 场景 | 入口 | 约束 |
| --- | --- | --- |
| PVE API、VM cloud-init 用户材料 | `environments/astra/runtime/.env.pve-opentofu.tpl` | 通过 1Password 运行时注入；模板只含变量名。 |
| OPNsense API | `environments/astra/runtime/.env.opnsense.tpl` | 通过 `op run --env-file … --` 注入。 |
| 交换机 SSH | `environments/astra/runtime/.env.switch.tpl` | 通过 `op run --env-file … --` 注入。 |
| VM baseline egress / K3s | 仓库外显式路径 | 仅允许受限权限的 JSON；不得把解析后的值放到 CLI、inventory、facts 或日志。 |

### Runtime 模板变量

下表是三个仓库内 runtime 模板的完整变量接口。左列是命令实际读取的环境变量，
不是可以填入 Git 的示例值；`op://…` 引用仅保留在 `.tpl` 中，由 1Password 在
子进程启动时解析。修改变量名、将秘密改写为明文，或在 shell 中临时覆盖这些
变量，都会绕过当前已审查的运行时边界。

| 模板 | 变量 | 用途与约束 |
| --- | --- | --- |
| `.env.pve-opentofu.tpl` | `TF_VAR_pve_endpoint` | PVE API endpoint，供 OpenTofu provider 使用；必须指向本次经确认的 API。 |
| 同上 | `TF_VAR_pve_api_username`、`TF_VAR_pve_api_token_id`、`TF_VAR_pve_api_token_secret` | PVE API 身份与 token；均为秘密或身份材料，不输出、不提交。 |
| 同上 | `TF_VAR_pve_insecure` | OpenTofu provider 的 TLS 证书验证开关。当前模板明确为 `true`；这是安全例外，变更前必须核对 endpoint、证书部署和风险接受，不能默认为安全。 |
| 同上 | `PVE_VM_CLEMON_PASSWORD`、`PVE_VM_CLEMON_PUBLIC_KEY` | `clemon` 初始 cloud-init 用户的密码与 SSH 公钥；仅在渲染时使用。 |
| 同上 | `PVE_VM_OPS_PASSWORD`、`PVE_VM_OPS_PUBLIC_KEY` | `ops` 自动化 cloud-init 用户的密码与 SSH 公钥；仅在渲染时使用。 |
| `.env.opnsense.tpl` | `OPNSENSE_API_KEY`、`OPNSENSE_API_SECRET` | OPNsense 管理 API 凭据；只能交给受控 playbook 子进程。 |
| `.env.switch.tpl` | `SWITCH_SSH_USER`、`SWITCH_SSH_PASSWORD` | 交换机 SSH 身份与密码；不得出现在 inventory 或 playbook `-e` 参数中。 |
| 同上 | `SWITCH_SSH_PORT` | SSH TCP 端口，当前模板为 `22`；如目标设备不同，先在受控模板引用/运行时材料中审查后调整。 |

K3s 运行时 JSON 的键为 `op://vault/item/field` 形式的外部引用，值为该动作需要
的实际秘密。加载器拒绝符号链接、非普通文件、组/其他用户可读文件和空映射。
创建后应至少执行 `chmod 600 <file>`，且文件必须位于仓库外。

示意形状（仅展示键和值类型，不是可提交文件）：

```json
{
  "op://vault/item/server-token": "<redacted>",
  "op://vault/item/registry-auth": "{\"username\":\"<redacted>\",\"password\":\"<redacted>\"}"
}
```

## 0.5 变更记录与停止规则

每次在线变更至少记录：目标范围、操作者、开始/截止时间、已验证的前置条件、
恢复/控制台路径、实际命令、输出摘要、接受的告警、结束状态和后续动作。

出现以下任一情况立即停止向下一阶段推进：范围不明确；配置校验失败；凭据或
受保护文件不符合要求；在线检查返回 `FAIL`；无法解释的 `WARN`；未验证的
回退路径；或拟执行操作超出本章声明的所有权。保留现有证据，重新作出范围和
恢复决策；不要用删除 state、跳过检查、临时放宽权限或手工改生成物绕过。

## 0.6 基础服务前置项

`environments/astra/inventory/foundation.yml` 描述集群外基础服务的恢复元数据。
它包含 OPNsense、TrueNAS、内部 DNS、sing-box、Harbor、外部数据库和
Authentik 的依赖、健康探针、恢复顺序和 break-glass 引用。这里的内容是
元数据和恢复规划，不会部署或修复这些服务。

在创建 K3s 节点前，至少确认标有 `required_before_k3s: true` 的服务具备符合
实际环境的可达性、恢复路径和责任人。完整的证据规则见
[全链路验收与恢复](06-acceptance-and-recovery.md)。
