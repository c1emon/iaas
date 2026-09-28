## 1. 实现准入与当前合同

- [x] 1.1 按用户授权创建 `feat/pve-template-acceptance-and-snippet-cleanup`；切换前工作树干净，规划文件已在 main，无未提交内容需要处置。
- [x] 1.2 将合同草案落实为当前 request/result 校验及 JSON schema，包含 origin 的互斥证据分支、retry_of/retry_materials 的首次/补执行规则、状态、摘要绑定、执行授权与标准 reason codes；拒绝未知版本和扩展删除范围。
- [x] 1.3 建立供 IaaS/infra-ops 共用的正常和拒绝样例，同一份 fixture 由合同测试加载；不伪称样例即现场结果。

## 2. 受控 snippet 清理

- [x] 2.1 绑定原 VM 及所有权材料：deployment 复用 manifest＋保存计划＋pve-result 与删除/state 写回关联；acceptance 使用原 request/journal、创建/删除授权和临时 VM 删除确认。共享清理检查，不访问 state，不允许切换来源规避证据。
- [x] 2.2 实现 VM 缺席、节点/共享存储范围及完整 VM/模板引用检查；权限不足、pending/snapshot 或别名范围不明时 fail closed。
- [x] 2.3 实现精确文件 helper、删除前摘要/路径检查、互斥、缺席幂等与删除后复核；更新最小安装/sudo 权限及 bootstrap 文档。
- [x] 2.4 支持新补清理执行加载 retry_materials、核验 retry_of/原摘要/完整清单及原任务已终止，再全部重新检查，输出分项结果和残留；允许验收 VM 删除后单独收尾 snippet，不重复删 VM、写 state、解锁或扩大清单。

## 3. 新模板最小验收

- [x] 3.1 固定模板发布身份、临时 VM 资源/网络上限、只读检查、注入值、工作/清理期限及创建删除授权；副作用前保留意图和一次性执行关联。
- [x] 3.2 使用已有 API/UPID 通道实现 full clone、磁盘/启动核验、临时配置及启动；拒绝 VMID 冲突，保留新对象及卷的准确归属。
- [x] 3.3 实现固定 guest-agent、cloud-init 和本次 hostname 检查，无 SSH/外网/修复依赖。
- [x] 3.4 实现失败/超时 finally 收尾、临时 VM/卷/snippet 清理和源模板前后复核；未知归属或活动任务保留，结果分为 passed/failed/unknown。
- [x] 3.5 落实 caller 一次性分派边界及显式 start/observe；校验原目录中的执行/请求/目标/admission 关联，冲突拒绝、缺核心材料 unknown 且零 PVE 写入；断线/响应丢失不自动重放 mutation。

## 4. launcher、测试与交付

- [x] 4.1 暴露 accept/snippet-cleanup 及只读原执行查询，声明 start 写入与 observe 只读效果，完成 original_execution_dir/cleanup_evidence_dir 的只读文件发现及 local/DinD 传输；更新 capability/version，保留 TLS、SSH 主机校验、凭据隔离及脱敏。
- [x] 4.2 运行模板成功、检查失败/超时、清理失败、跨 Runner 重复观察/缺材料；snippet 正常/缺席/引用/摘要不符/权限不足/部分失败，以及 retry_of 合法/非法绑定、无 state 验收遗留 snippet 和来源切换拒绝的定向测试。
- [x] 4.3 运行改动相关 Python/Go、lint、schema/OpenSpec 校验及提交前图变更检查；记录实际覆盖范围，不做无依据的全量扩张。
- [x] 4.4 交付稳定合同入口、双方共用正反例、launcher 调用示例、helper 最小权限和版本说明；明确 infra-ops 只在必需检查与清理全部通过后推广。

真实 PVE 验证不作为上述软件任务的隐含阶段；另行提供固定目标和创建/删除授权窗口后，仅执行一次代表性验收。当前不执行发布、合并、现场操作或 infra-ops 修改。
