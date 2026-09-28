## Context

当前代码已有 `pve-template-record/v2`、HTTPS publisher、UPID 观察、受保护任务材料和完整 execution admission。VM 完整克隆通过 OpenTofu 实现；模板临时验收尚无入口。`cloud_init_helpers/artifacts.py` 的 manifest 已记录 VMID、file_id、文件名及 SHA-256；`iaas-pve-snippet-upload` 仅支持上传与核验，不能直接作为删除通道。

普通 `pve verify` 针对保存计划的配置预期；现有 Ansible guest 验证依赖 guest SSH，且部分不可达仅警告。两者均不能代替此次必需的 guest-agent/cloud-init 验收。

## Decisions

### 1. 两个明确入口，保留原生命周期

拟增加 `pve-template accept` 和 `pve snippet-cleanup`，均由 `iaas run` 调用；start 模式标记 `network=true`、`infrastructure_write=true`、`state=false`，observe 为只读观察且无 PVE/state 写入。固定请求和已有执行准入直接授权动作，无需另外设计审批或预览协议。使用现有规范化摘要绑定请求与 admission；不让调用方拼接原生命令。

`accept` 通过已有 HTTPS 客户端及 native task 观察机制驱动临时 full clone。该 VM 明确归本次验收执行所有，不进入普通 VM OpenTofu state；不增加临时 root、S3 state 或 create/destroy 两套计划。普通长期 VM 继续走现有 plan/apply。补清理入口根据来源只读普通部署的原删除计划/执行材料，或临时验收的原 request/journal/删除确认；两者均不运行 OpenTofu、不读取或修改实时 state backend。

新 request/result 使用独立 kind 的 v1，保留现有 publication preview/result/record 版本；不向普通 `pve-result` 混入新的 guest 责任定义。接口详见 [合同草案](contracts/pve-acceptance-cleanup-v1.md)。

### 2. 所有权与未知状态先于清理

首次副作用前，持久化 execution ID、请求摘要、固定目标及创建意图。调用方沿用完整 execution admission，互斥覆盖模板、VMID、存储/snippet 保护域及所有有关写入方；共享存储不能仅以节点锁代替。API clone 的 occupied conflict 必须拒绝，预检查 free 不构成占用权。

临时 VM 归属至少结合原任务、准确目标、创建结果及后续 native identity，不能只看 VMID、名称或自报标签。记录本次创建的磁盘、cloud-init/EFI 等卷；源卷和继承的共享资源绝不自动纳入清理。无法证明归属或原操作停止时，保留并报告。

两个入口显式选择 `options.execution_mode: start|observe`，不设默认值。start 前，调用方在已有消费记录及互斥内原子确认从未分派，并先记已分派后调用 runtime；runtime 先保留 request/admission 关联和 journal 再产生副作用。跨 Runner 一次性分派由调用方负责，现有 admission 校验不查询其台账，可复制的文件不是全局去重保证，也不为此新建 IaaS 台账。

已分派或是否分派未知，只能 observe；通过 `files.original_execution_dir` 显式只读映射原 request/journal/已有 result，校验 operation、execution ID、request digest、target 和 reservation/pending 关联。result 缺失保留部分事实，核心材料缺失为 unknown/非成功且零 PVE 写入，不能回到 start。输入冲突拒绝；换 output、Runner 或新 reservation 不能自动重跑原任务。现有 launcher 的新 output 可用于收集观察结果，但不得覆盖原目录。

### 3. 最小检查与收尾

顺序为准入 → full clone/任务完成 → 磁盘及启动声明核验 → 临时配置/cloud-init → start/任务完成 → guest-agent 响应 → cloud-init 完成且无失败 → 本次 hostname 匹配 → 清理 → 源模板复核 → 结果。

固定检查集禁止 caller 自定义 shell。hostname 为 v1 唯一注入验收字段，要求与已知模板基线不同并绑定本次执行；只验证 agent 返回的原有 hostname 不算成功。cloud-init 必须实际报告完成且无错误，缺工具、禁用、未运行、错误/降级或不可解析不能通过；轮询有明确期限，不在 guest 中修复配置或重新运行 cloud-init。

工作期限与 cleanup 预算分开。检查失败或工作超时仍进入 finally 收尾；先确认克隆/启动任务终止和所有权，再停止及删除准确临时 VM，核对所属卷消失，最后清理本次专属 snippet。没有生成 snippet 时该项为 `not_required`，不得把模板继承文件算作本次拥有。删除任务响应丢失时不得因为当前 VM 不可见便伪造原删除成功。

源模板使用前后 UUID、template flag、绑定卷和稳定配置比较；正常瞬时 native task lock 不作为配置变更。该核验加只向 clone 写入的调用约束不等于全盘字节完整性证明，不新增逐磁盘 hash。身份/配置发生变化即失败，不做自动恢复；无法复核则未知。

### 4. snippet 清理的边界

清理请求以 `origin` 区分 deployment 与 acceptance。deployment 保留原 VM/部署执行、已批准删除计划、原 manifest/上传记录及删除/state 写回关联；复用现有 manifest＋保存计划＋pve-result，不另建证据系统。acceptance 仅用于原临时 VM 已确认删除后的专属 snippet：使用原验收 request/journal、创建/删除授权、准确对象及原删除确认，不要求或伪造 plan/state。原材料必须证明来源，不能切换 origin 绕过要求；记录不足仍拒绝。

两种来源共用完整归属、引用、摘要、互斥与删除核验。首次独立 cleanup 的 `retry_of`、`retry_materials` 均为 null；再次补执行使用新 ID/admission，并提供前次 cleanup request/journal/已有 result 的只读引用。校验前次绑定、原任务已终止及完整清单不变后重新检查，不新增文件、不换摘要、不重建/重删 VM。所有证据经 `files.cleanup_evidence_dir` 只读映射，具体字段见合同。清理结果关联原验收但不改写它；VM/卷残留或任务未知不能由 snippet 清理通过掩盖。

在完整互斥上下文内确认 VM 确实不存在，确定存储的节点可见范围及共享性，检查全部相关 VM/模板配置引用，包含相关 pending/snapshot 配置；如实际平台不能完整读取，返回检查不完整，不删。HTTP 成功但受 ACL 过滤的资源列表不等于完整列表，必须有范围及权限完整性的依据。存储别名可能指向相同底层文件；无法排除别名引用时保留，不凭相同/不同 storage ID 猜测。

逐项核验与原记录相同的精确 volid、摘要、归属，删除前在受限通道内重新校验文件；禁止符号链接、路径逃逸、通配符。已知合法目标确实缺席可返回 `already_absent`；权限错误或无法解析路径不算缺席。其他安全独立条目可继续执行；全局范围/互斥检查失败时停止整批写入。

调用方互斥覆盖引用变更窗口；helper 的本地文件锁不能证明跨节点或非合作写入方已互斥。无法确认共享保护域时 fail closed，记录限制，不建设新的分布式锁服务。

### 5. helper、信任与凭据

优先复用现有受限 SSH 传输，新增专用 `iaas-pve-snippet-cleanup` helper，避免扩大 upload helper 的隐含权限。root-owned helper 与父目录不可由调用账户写入，建议沿用现有安装模式；sudo 只新增该固定程序，不授权 `rm`、shell、任意 `pvesm` 或编辑配置。helper 独立校验固定字段、路径、摘要和引用检查依据；不能把节点扫描不完整转交给 caller 布尔值跳过。

实现阶段需按选定 PVE 支持接口明确引用扫描在 API 与 helper 的分工，给出精确的权限清单和安装命令，覆盖共享范围、快照/pending 的代表性 fixture；不足则报告 unsupported/unknown，不用试删探测权限。远端系统 Python 属于节点 helper 依赖，本地开发仍通过项目 uv 环境管理。

保留当前 PVE TLS/私有 CA 规则、严格 SSH known_hosts、按动作筛选的凭据和日志脱敏。accept 不获得镜像下载凭据；snippet cleanup 不获得 S3 凭据。guest 输出、cloud-init 内容和 SSH 原始诊断留在受保护材料，公共结果只含批准字段与 reason code。

## Validation and risks

采用定向 fake API、helper 文件系统 fixture、launcher local/DinD 文件映射及隔离测试，不建立真实环境矩阵。覆盖成功、失败/超时、清理失败、重复调用，以及 snippet 缺席/引用/摘要/权限/部分失败；另保留身份替换、未知原操作和共享范围不完整的必要反例。

GitNexus 初次增量索引给出的上传函数 CRITICAL 调用图与源码不符；全量重建后 impact 为 LOW（直接调用 `cloud_init.main`，3 个上游影响符号），并与直接源码核对。全仓流程枚举仍有截断，不据此断言无其他影响。实现时对实际修改符号重新 impact，提交前 detect-changes。
