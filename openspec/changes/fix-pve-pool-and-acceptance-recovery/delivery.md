# 软件交付与现场边界

实施分支：`implement/fix-pve-pool-and-acceptance-recovery`。本 change 仅修改 IaaS。

当前合同：publication request v2、preview/result/record v3；acceptance request/result v3、preview v1；acceptance/recovery one-shot admission v2；recovery request/preview/result v1。新 start 不接受旧合同；rc.19 原验收 v2 仅供恢复读取。

节点需安装本版本 upload/delete helper 和 wrapper-only sudo 规则，并固定 SSH key/known_hosts。验收池权限继承的只读编译使用节点原生 PVE 权限模块；不写池或 ACL。普通/publication 无法证明未来权限时拒绝。已有 VM 的 pool 改为空值受 provider 0.111.1 限制，准入拒绝；新 VM 可不指定 pool。

软件验证：完整 Python 1792 passed、2 skipped；全项目 Pyright 0 errors、Ruff 通过、4 个 import contracts 保持；Go 全套通过；OpenTofu 模块 fmt 与锁定 provider fixture init/validate 通过；OpenSpec strict 通过。API/helper、local/DinD 传输均为软件 fixture，不能作为真实 PVE 或共享环境验收。

固定版本计划为 `v0.1.0-rc.20`；发布与 digest/launcher SHA256SUMS 核验尚未完成，不使用预测摘要。正式恢复输入与命令见 [操作说明](../../../docs/operations/pve-acceptance-recovery.md)。

task8.1 尚未执行：缺 run-120-1 受保护原材料、可唯一关联 guest exec 的可信403及当前限定清理批准。VM798、两盘和 snippet 的实际存在性仍未知；原验收没有通过或晋升结论。清理成功也不会改变原验收。
