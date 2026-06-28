# 全局代码审查整改路线图

本文记录 2026-06-27 全局代码/模块 review 及后续 council 评估后形成的分阶段整改计划。路线采用“均衡偏保守”策略：先补安全网和修确定 bug，再提高 cloud-init 可证明性，随后收敛 validation，最后按实际维护痛点做小范围去重。

它是后续 OpenSpec change、维护任务和实现排期的输入，不代表所有事项必须一次性完成。

当前状态：Phase 1 已通过 `fix-review-p1-remediations` 完成并归档；Phase 2 已通过 `make-cloud-init-snippet-verification-deterministic` 完成并归档；Phase 3a 已通过 `strengthen-pve-and-service-inventory-validation` 完成并归档。

## 目标

- 修复已确认会影响现有流程的 bug。
- 在不改变功能和入口的前提下补足最小安全网。
- 提高 PVE / cloud-init / Ansible / OpenTofu 自动化链路的可验证性。
- 前移 YAML source-of-truth 的输入校验，减少下游失败和隐式耦合。
- 降低重复实现和长期维护成本，但避免过度抽象。
- 保持离线校验与在线变更边界清晰。

## 执行原则

- 不做 big-bang rewrite；每个 change 只解决一个主题。
- 优先修真实 bug 和可验证性问题，再做组织性重构。
- 重构前后保持现有入口、生成物和默认离线行为一致，除非 change 明确声明行为变化。
- `scripts/common/` 只承载 primitive helper，例如 errors、I/O、基础 validation、CLI boundary；不要提前抽 domain framework。
- cloud-init 只追求“单次 artifact 生命周期 deterministic”，不追求跨次密码 hash 完全一致，也不固定长期 salt。
- OpenTofu protected / unprotected 双 resource 暂不合并；优先增加说明和一致性检查。

## Phase 0：最小安全网

目标是在重构前建立“功能一致性”判断基线。

- [ ] 增加或确认生成物等价检查。
  - 重点文件：
    - `infra/tofu/pve/generated.auto.tfvars.json`
    - `ansible/inventories/generated/pve.yml`
    - `docs/generated/pve-vms.md`
    - `docs/generated/services.md`
    - `infra/packer/proxmox/debian-13/template-build.env`
  - 要求：重构前后除预期变更外 diff 为空。
- [ ] 增加最小 negative validation tests。
  - 覆盖非法 VM name、Ansible group、PVE tag、static IP。
- [ ] 增加 CLI validation error 行为测试。
  - 要求：exit code 为 1，无 Python traceback，错误消息包含字段路径，不泄露 secret。
- [ ] 明确离线边界验收。
  - `make check` 不访问 PVE、OPNsense、switch，也不执行 mutation。

验证建议：

- 运行 `make check`。
- 记录当前 generated outputs 的预期 diff 基线。

## Phase 1：P1 止血与低风险修复

目标是消除已知自相矛盾、失效入口和明显文件卫生问题。

- [x] 对齐 `ops` sudo policy 与 guest verification。
  - 相关位置：`inventory/pve-cluster.yml`、`ansible/playbooks/pve/tasks/verify-guest.yml`
  - 当前状态：`ops` 作为自动化用户使用受控 `NOPASSWD`；`clemon` 保持交互式 sudo。
  - 约束：guest verification 继续把 `sudo -n true` 作为硬检查，且 root SSH / SSH 密码登录保持关闭。
- [x] 删除、归档或修复失效 legacy smoke 脚本。
  - 当前状态：旧 switch smoke 入口已退役；新的 switch 行为应落在当前 collection / test surface。
- [x] 修正文档中与 inventory 不一致的节点信息。
  - 重点：`docs/architecture.md` 中 PVE node3 管理 IP 与 `inventory/pve-cluster.yml` / validation 事实一致。
- [x] 清理并隔离运行时产物。
  - 重点：`infra/tofu/pve/terraform.tfstate*`、`.terraform/`、`.venv/`、`.cache/`、`ansible/collections/`、`.DS_Store`
  - 要求：确认未被 Git 跟踪；必要时迁出仓库工作树或使用远端 backend / 专用 ignored state 目录。
- [x] 统一 CLI 对 `ValidationError` 的边界处理。
  - 相关位置：`scripts/pve_inventory/cli.py`、`scripts/services_inventory/cli.py`
  - 目标：输入错误输出稳定、可读，不泄露 Python traceback。
- [x] 将 `static_ip` 解析异常包装成带上下文的 validation 错误。
  - 相关位置：`scripts/pve_inventory/vm_validation.py`

验证建议：

- 运行 `make check`。
- 对被修复的脚本入口运行最小 smoke 命令，或删除后确认无 Makefile / docs 引用。
- 检查 `git ls-files '*.tfstate*'` 为空。

## Phase 2：cloud-init deterministic artifacts 与 checksum verify

目标是让 upload / verify 能证明 PVE 节点上的 snippet 内容等于当前流程生成的本地 artifact。

- [x] 将 cloud-init upload / verify 改为单次 render 产物驱动。
  - 相关位置：`scripts/pve_inventory/cloud_init.py`
  - 目标：一次流程内复用同一批本地 rendered snippets，避免 upload 和 verify 分别重新生成内容。
- [x] 生成 manifest / checksum。
  - 建议内容：snippet 文件名、目标节点、sha256、生成时间、输入 inventory 标识。
- [x] upload 使用 exact rendered files。
  - 要求：upload 阶段不得隐式重新 render 另一批内容。
- [x] 为 PVE node wrapper 增加内容校验能力。
  - 相关位置：`infra/pve-node/bin/astra-pve-snippet-upload`
  - 目标：支持 checksum verify，例如 `--sha256 EXPECTED` 或等价接口。
- [x] 处理密码 hash 随机 salt 对一致性校验的影响。
  - 相关位置：`scripts/pve_inventory/secrets.py`
  - 目标：同一 apply/verify 流程不因重复 render 产生不同 hash。
  - 非目标：不要为了跨次 diff 稳定而固定长期 salt。
- [x] 给 cloud-init upload / verify 的 SSH subprocess 增加 timeout。
  - 相关位置：`scripts/pve_inventory/cloud_init.py`
- [x] 增加 stale remote snippet 测试。
  - 场景：远端文件存在且 YAML 合法，但内容不是当前本地期望，verify 必须失败。

验证建议：

- 新增/更新 Python 单元测试覆盖 checksum mismatch。
- 手工或集成验证：upload 后 verify checksum 一致；手动篡改远端 snippet 后 verify 失败。

## Phase 3a：PVE 与 services inventory validation hardening

目标是让 source-of-truth 的常见错误尽早、稳定地暴露在 validation 层。

- [x] 强化 VM name / hostname / Ansible group / PVE tag / static IP 校验。
  - 相关位置：`scripts/pve_inventory/vm_validation.py`
  - 建议约束：
    - VM name / hostname：限制为 DNS/hostname 安全字符。
    - Ansible group：限制为 Ansible inventory group 安全字符。
    - PVE tag：限制为 PVE/provider 可接受字符集。
    - list 字段：元素必须为非空 string，重复项显式处理。
- [x] 为 services Markdown renderer 增加表格转义。
  - 相关位置：`scripts/services_inventory/render.py`
  - 重点：转义 `|`、换行等会破坏 Markdown table 的字符。
- [x] 保持当前 `inventory/*.yml` 全部通过。
  - 如果新规则暴露现有非法值，应优先判断是输入确实错误，还是规则过窄。

验证建议：

- 增加负向测试覆盖非法 VM name、group、tag、static IP、Markdown 特殊字符。
- 确保现有 inventory 仍能生成相同或预期更新后的输出。

## Phase 3b：OPNsense vars validation（后置，可单独 change）

目标是提高防火墙/网关变更前的输入安全性，但不把它混入 PVE inventory 重构。

- [ ] 为 OPNsense vars 增加 schema / preflight validation。
  - 相关位置：`ansible/playbooks/opnsense/`、`ansible/vars/opnsense/`
  - 重点：interface/name、ports、net、bool 字段、unknown keys。
- [ ] 优先考虑 Ansible 侧 assert / schema，而不是强行纳入 Python PVE inventory pipeline。
- [ ] check mode 输出应明确区分“将创建 / 将修改 / 无变化”。

验证建议：

- 增加 OPNsense vars 非法值负向测试。
- 对 mutation playbook 保持 check mode 可审查。

## Phase 4a：小范围 common primitives 抽取

目标是减少明显重复，但避免把 `scripts/common/` 做成大杂烩或过早 domain framework。

- [ ] 提取共享 primitive helper。
  - 建议位置：`scripts/common/`
  - 候选内容：
    - errors
    - I/O
    - 基础 validation helper
    - Markdown escaping
    - CLI boundary / output helper
- [ ] 解除 `services_inventory` 对 `pve_inventory` 内部 helper 的隐式依赖。
  - 相关位置：`scripts/services_inventory/*`
- [ ] 不在本阶段重组所有 domain 目录。

验证建议：

- 重构前后运行 `make check`。
- 生成物除预期变化外保持一致。

## Phase 4b：PVE API / runtime adapter consolidation（后置，可选）

目标是降低 online 检查层行为分叉，但不急于合并底层实现。

- [ ] 先统一 facade / protocol / error / redaction，而不是强行合并 `urllib` 与 `proxmoxer` 底层 client。
  - 相关位置：`scripts/pve_inventory/preflight_api.py`、`scripts/pve_inventory/pve_api/client.py`
- [ ] 合并或统一 runtime config parsing。
  - 相关位置：`scripts/pve_inventory/preflight_config.py`、`scripts/pve_inventory/health.py`
- [ ] 保留 fake client 测试，避免 online 行为回归。

验证建议：

- preflight / health 的 env parsing、timeout、TLS、redaction 行为有测试覆盖。
- online 访问仍保持显式入口，不进入 `make check`。

## Phase 5：低风险维护性清理

目标是整理长期维护成本低、回滚简单的事项。

- [ ] 为 OpenTofu protected / unprotected VM resource 加注释和一致性检查。
  - 相关位置：`infra/tofu/modules/pve-cloudinit-vm/main.tf`
  - 说明：由于 `lifecycle.prevent_destroy` 的限制，不建议贸然合并。
- [ ] 整理 OpenSpec active changes。
  - 目标：verify / archive 已完成 change，降低规格漂移。
- [ ] 清理空目录、legacy 目录和过期说明。
  - 重点：空目录用途说明、过期迁移入口、无效 Ansible filter path 等。
- [ ] 评估未使用依赖和本地运行时目录策略。
  - 目标：降低依赖面，避免仓库结构被本地 cache/provider/collection 产物污染。

验证建议：

- 运行 `make check`。
- 对 OpenTofu 双 resource 增加结构一致性检查，避免后续只改一边。

## 建议的 OpenSpec change 切分

可直接小修的事项无需强制走 OpenSpec；涉及行为、验证语义或跨模块流程的事项建议走 OpenSpec。

推荐切分：

1. `fix-review-p1-remediations`（已完成并归档）
   - sudo policy；
   - legacy smoke；
   - CLI error boundary；
   - 文件卫生；
   - 文档不一致。
2. `make-cloud-init-snippet-verification-deterministic`（已完成并归档）
   - manifest/checksum；
   - exact file upload；
   - remote checksum verify；
   - timeout；
   - password hash artifact 策略。
3. `strengthen-pve-and-service-inventory-validation`（已完成并归档）
   - VM name/hostname；
   - Ansible group；
   - PVE tag；
   - static IP；
   - services Markdown escaping。
4. `strengthen-opnsense-vars-validation`
   - 单独后置，不混入 PVE inventory validation。
5. `extract-python-common-primitives`
   - 只提取 errors / I/O / validation primitives / CLI boundary。
6. `consolidate-pve-api-runtime-adapters`
   - 后置可选。

## 必须满足的功能一致性验收

- `make check` 不访问 PVE、OPNsense、switch，不执行 mutation。
- 生成物除预期变更外 diff 为空。
- validation error exit code 为 1，无 Python traceback，错误消息带字段路径，不泄露 secret。
- cloud-init 单次 render 生成 manifest/checksum；upload 使用 exact rendered files；verify checksum mismatch 必须失败。
- 明确 `ops` 是 automation user 还是 interactive user，并让 sudo policy 与 guest verification 一致。
- 当前 `inventory/*.yml` 全部通过 validation。
- 非法 VM name/group/tag/static IP 有负向测试。
- services Markdown 特殊字符不会破坏表格。
- `git ls-files '*.tfstate*'` 为空；`.terraform/`、`.venv/`、`.cache/`、`ansible/collections/` 不进入 tracked files。

## 需要避免的反模式

| 反模式 | 风险 | 建议 |
|---|---|---|
| 过度抽象 `scripts/common/` | common 变成大杂烩 | 只放 primitive，不放 domain policy |
| 过度 schema | inventory 演进困难 | schema 与 homelab policy 分层 |
| 固定 password salt | 降低安全性 | 不追求跨次 hash deterministic |
| Golden tests 过多 | 测试脆弱、维护成本高 | 只 snapshot committed outputs 和关键边界 |
| PVE API 强行合并 | 线上行为回归 | 先 adapter，后底层合并 |
| OpenSpec change 过大 | review / rollback 困难 | 一个 change 一个主题 |
| OPNsense Python schema 过深 | 跨语言耦合 | 优先 Ansible assert / schema |

## 优先级摘要

| 优先级 | 事项 | 阶段 |
|---|---|---:|
| P1 | `ops` sudo policy 与 guest verification 冲突（已完成） | 1 |
| P1 | legacy switch smoke 入口已退役（已完成） | 1 |
| P1 | cloud-init snippet verify 不校验内容（已完成） | 2 |
| P1/P2 | 运行时产物混在工作树（已完成：tracked-file hygiene） | 1 |
| P1/P2 | 最小功能一致性安全网不足 | 0 |
| P2 | VM name / group / tag / static IP 校验不足（已完成） | 3a |
| P2 | services Markdown 未转义（已完成） | 3a |
| P2 | OPNsense vars schema 偏弱 | 3b |
| P2 | `services_inventory` 依赖 `pve_inventory` 内部 helper | 4a |
| P2 | PVE API client / runtime config 重复 | 4b |
| P2 | OpenTofu protected / unprotected resource 缺少一致性保障 | 5 |

## 推荐路线

首选路线：

1. Phase 0：最小安全网。
2. Phase 1：P1 止血。
3. Phase 2：cloud-init deterministic artifacts。
4. Phase 3a：PVE 与 services validation hardening。
5. 视维护痛点选择 Phase 4a。
6. Phase 3b / 4b / 5 后置，按需要单独推进。

不推荐一次性推进所有阶段。
