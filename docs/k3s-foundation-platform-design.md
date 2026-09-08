# K3s 与外部平台的设计边界

本仓库提供 K3s 节点生命周期实现；环境选型、主机布置和共享平台的部署计划由
调用方维护。这里不预设节点数量、物理机器、存储品牌、域名或基础服务单点。

运行时消费显式 K3s intent 和 VM Ansible inventory，校验节点成员、角色、架构、
网络职责、固定版本及 artifact checksum。VM 来源、节点地址、基础服务依赖和
恢复材料由调用方声明，不能从测试 fixture 推导实际环境。

| 边界 | 当前职责 |
| --- | --- |
| IaaS runtime | VM/cloud-init、guest baseline、K3s preflight/deploy/verify、受限 snapshot/upgrade、非秘密 handoff |
| 环境调用方 | 拓扑、失败域、目标节点、版本选择、凭据解析、运行授权、备份与环境验收 |
| 外部 platform repository | CNI、CSI、Gateway、GitOps 和其他集群内期望状态及其验收 |
| application repositories | 应用发布、配置和应用路由 |

多网卡配置使用显式角色选择 K3s node identity；管理、cluster underlay、存储和
入口路径按意图区分。运行时不会据此创建交换机 VLAN、防火墙规则或存储系统。
当前 CNI 外置的流程可能停在 `CNI-not-initialized`；这是受限的节点阶段结果，
不能表示集群网络或应用平台已就绪。

可执行命令、输入 schema、凭据与升级限制见 [K3s 操作章节](operations/05-k3s.md)。
基础服务恢复元数据和证据边界见 [验收与恢复](operations/06-acceptance-and-recovery.md)。
环境实际设计和历史运行记录应保存在调用方环境仓库。
