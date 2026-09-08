# 6. 全链路验收、基础服务与恢复边界

本章把交换机、OPNsense、PVE、VM 与 K3s 的证据串成一次实际环境验收。它不把
离线测试、synthetic fixture、缺失凭据导致的 `SKIP` 或仅有设计文档表述为已部署、
高可用或生产资格。

## 6.1 基础服务与恢复元数据

`$ENVIRONMENT_DIR/inventory/foundation.yml` 是基础服务恢复元数据的源文件。它
不部署任何服务，但为每个恢复单元记录以下字段：

| 路径 | 含义 | 使用边界 |
| --- | --- | --- |
| `foundation_hosts[]` | `name`、`kind`、管理身份、额外地址、单点风险和备注。 | 用于恢复定位，不替代设备 inventory 或凭据。 |
| `foundation_services[]` | 服务名、host、runtime、tier、依赖、是否 K3s 前置。 | 定义恢复/验证顺序。 |
| `required_before_k3s` | K3s 之前必须就绪的服务标记。 | 必须以实际可达/恢复证据确认。 |
| `restore_order` | 恢复排序编号。 | 必须与 `dependencies` 一致；不是自动恢复计划。 |
| `health_check` | `type`、`target`、预期 HTTP 状态/DNS 答案等。 | `make foundation-health` 是在线只读探针。 |
| `backup_restore` | profile 与现行恢复手册路径。 | 记录责任与材料，不产生备份。 |
| `break_glass` | 方法、访问路径、外部 secret reference。 | 值不得打印或提交。 |
| `known_risks` | 已接受风险。 | 必须在验收记录中保留，而不是隐藏。 |
| `storage_networks` / `k3s_storage_access` | TrueNAS 存储网与 phase 访问范围。 | 限定为 VM K3s 节点；不自动配置交换机/防火墙。 |

恢复前置序列由调用方的依赖声明和 `required_before_k3s` 决定，不预设服务品牌
或固定机器。具体地址、服务状态和
恢复材料必须从当前环境与受保护系统确认，不能只从静态 YAML 推断健康。

服务元数据 `$ENVIRONMENT_DIR/inventory/services.yml` 使用 `services[]` →
`name`、`owner_vm`、`description`、`endpoints[]`；endpoint 可含 `name`、`fqdn`、
`port`、`protocol`、`exposure`、`auth`、`dns_hint`、`reverse_proxy_hint`、
`opnsense_hint`。这些是声明式文档元数据，不会创建 DNS、Reverse Proxy、NAT 或
防火墙规则。运行 `make services-check` 确保生成的
`$GENERATED_DIR/docs/services.md` 未过期。

## 6.2 分阶段验收矩阵

| 阶段 | 最低证据 | 不足以证明 |
| --- | --- | --- |
| 交换机 | 原生 readonly facts、审查后的 plan、管理路径和目标 VLAN/端口实际连通。 | YAML 语法正确或接口模块成功。 |
| OPNsense | API readonly/export、目标规则/VIP/网关身份和实际数据面路径。 | API HTTP 成功或导入的静态 export。 |
| PVE | `make pve-health`、必要时 `pve-preflight`、模板/bridge/storage 的 live 事实。 | `make pve-check`、OpenTofu validate 或旧 state。 |
| VM | `make pve-verify-guests`、SSH/sudo、qemu agent、IP/gateway/DNS 事实、baseline 输出。 | cloud-init 文件已渲染或 Ansible syntax check。 |
| K3s | `k3s-preflight`、部署/验证输出、API、etcd、服务和每个节点注册。 | 单元测试、rendered review 或 bootstrap server 单点 ready。 |
| 平台 | CNI Pod/Service 连通、Gateway/LB、CSI、Registry/DNS 故障路径、GitOps 恢复。 | `CNI-not-initialized` 或 K3s API 可用。 |

验收记录需注明每项证据发生的时间、环境、scope、执行者、结果、告警、未覆盖项
及结论等级。只有所有相应 live 验证通过后，才可描述为该范围内“已部署”；是否
高可用还取决于独立物理故障域、quorum、存储与网络路径，不能由三个 VM 数量
自动推断。

## 6.3 端到端启动检查表

1. 运行 [准备](00-preparation-and-conventions.md) 的离线门禁，并保存版本与
   generated-output 新鲜度结果。
2. 对交换机执行只读事实和审查后的 plan；确认 PVE/OPNsense/存储/K3s 所需的
   VLAN/port 路径。
3. 对 OPNsense 执行 API readonly/export；确认管理、软件源、artifact、registry、
   DNS、K3s API/etcd 和存储路径的实际规则/路由边界。
4. 对 PVE 执行 health/preflight，确认模板、storage、bridge、mapping、控制台和
   VM 变更计划；创建后验证每台 guest。
5. 将 VM baseline、APT/代理/信任材料收敛到目标节点并重新验证 guest。
6. 组合并审查 K3s intent，运行 preflight，然后以完整 scope 部署并验证。
7. 停在 CNI 中间态时明确记录“控制面完成、平台未完成”；只有另行完成 CNI/
   storage/ingress/GitOps 验证后才允许承载对应工作负载。
8. 记录 snapshot/upgrade 的真实证据和缺少的 restore 演练；不要将节点本地
   snapshot 标注为灾难恢复完成。

## 6.4 停止、回退与恢复责任

| 位置 | 可安全停止点 | 当前不提供的自动化 | 人工恢复责任 |
| --- | --- | --- | --- |
| 交换机 | readonly 或 plan 后、apply 前。 | 工厂重置、原始 CLI 回滚。 | 使用控制台和已审查的逐端口恢复方案。 |
| OPNsense | API readonly/export 后、各资源类别之间。 | DNS/DHCP/接口/默认路由/DNAT 自动接管。 | 使用本地控制台、已保存配置和明确对象回退。 |
| PVE | plan 后、每个 VM/节点维护步骤之间。 | 自动迁移、Ceph flag、包回滚、state 修复。 | 使用 PVE console、备份、工作负载处置记录。 |
| VM | policy syntax 后、每个明确 host/limit 之间。 | 网卡/路由/DNS 回滚、未知 source 删除。 | 使用上一份 policy 或 VM console 恢复。 |
| K3s | preflight/render 后、bootstrap 前；串行节点步骤失败时。 | 自动 restore、retention、uninstall、node removal。 | 停止后保留 model/日志摘要，按单独 DR 设计恢复。 |

任何阶段的失败都不授权跨层“快速修复”：例如不允许因为 K3s 下载失败而手工改
APT proxy、因为 VM 不通而直接改交换机 trunk、因为 PVE state 漂移而删除 state，
或因为 CNI 未装而宣称 K3s 验收完成。重新回到拥有该配置的章节，形成新的明确
变更范围。

## 6.5 当前已知限制与后续准入

- PVE 节点数量和 VM 分布不自动形成独立物理故障域；单点风险由调用方声明并验收。
- K3s embedded-etcd 快照目前仅为 root-only 节点本地文件，没有异地副本、保留、
  加密、restore 校验或恢复演练。
- Cilium、Gateway、TrueNAS CSI、Flux 和应用 GitOps 没有当前可执行实现；它们
  需要独立的设计、配置、变更、live 验证和恢复材料。
- 调用方声明的基础服务依赖，其 YAML 元数据并不等于备份存在或恢复成功。

在这些限制被实际验证并记录前，结论应限定为“已完成本手册中相应自动化/人工
阶段的已覆盖证据”，而非“生产就绪”或“灾难恢复已验证”。
