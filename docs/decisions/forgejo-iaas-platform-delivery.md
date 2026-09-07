# Forgejo 驱动的 IaaS 与基础平台交付设计

记录日期：2026-09-07。

状态：设计方向已确定，待分阶段实施。本文记录后续任务，不表示真实环境已部署、
交接或验收。现有代码和已归档 OpenSpec change 是复用起点，仍需验证真实调用链。
本文不直接修改现行规格；涉及实现和契约调整时另建对应 OpenSpec change。

## 目标与范围

通过公开通用实现、私有环境配置和本地 CI，完成 VM、K3s 及基础平台部署。
本阶段终点是所选拓扑下集群具备承载应用的基础能力，不部署普通业务应用。

基础平台包括 Cilium、Flux、CSI/StorageClass、Gateway/入口地址、证书管理和
基础可观测性。允许使用临时 Pod、PVC 和测试路由验证能力，验收后清理。
功能可用不等同于完整 HA、灾难恢复、容量或生产资格验证。

## 仓库与执行职责

以下仓库名称是逻辑名称，真实地址、负责人和发布位置仍需确定。

| 位置 | 职责 | 交付或输入 |
| --- | --- | --- |
| GitHub `iaas` | 通用 Python、Ansible、OpenTofu 等实现与版本发布 | OCI 运行镜像、通用配置接口 |
| Forgejo `astra-ops` | 私有环境 inventory、策略、OpenTofu root、版本选择与基础设施流水线 | 环境配置提交、固定镜像 digest |
| Forgejo `platform` | 平台 bootstrap 自动化和集群基础组件期望状态 | Cilium 引导参数、Flux 及平台声明 |
| Forgejo Actions / Runner | 执行校验、plan、授权部署和一次性 bootstrap | 仓库配置与运行时注入凭据 |
| 目标集群内 Flux | 持续收敛基础平台状态 | 平台仓库的明确 revision 与路径 |

第一阶段采用 Forgejo Actions 与 Forgejo Runner，不引入 Drone。
普通 CI 与具有管理网访问能力的 infra runner 分开部署。Runner label 仅用于任务
匹配，不能当作权限隔离；需要验证所选 Forgejo 版本中实际可用的仓库、工作流、
触发者和部署凭据访问控制，再落实部署授权方式。

Forgejo 与引导 Runner 位于目标 K3s 之外。Forgejo 首次安装由管理机执行可重复
的安装流程，随后再接入 CI 维护，避免引导依赖循环。

## 打包、配置与状态

先发布一个 OCI 运行镜像，包含通用实现、Ansible 资源、OpenTofu modules 和
锁定的执行工具依赖。Python wheel、独立 Ansible Collection 或 module registry
仅在实际复用需要出现后再拆分。

- 镜像不包含真实 Astra 配置、凭据、kubeconfig 或 OpenTofu state。
- 私有配置仓库固定镜像 digest，运行时传入环境目录、输出目录和明确操作参数。
- 通用实现不得依赖仓库内固定 Astra 路径；环境 OpenTofu root 必须能引用镜像内
  随版本交付的通用 modules，或其他明确锁定的模块发布物。
- 凭据通过受保护的运行时通道注入；CI 不能依赖开发者电脑或交互式 1Password 登录。
- OpenTofu state 使用持久化后端和锁，同一环境串行 apply；部署关联配置提交、
  镜像 digest 和对应 plan。plan 可能包含敏感数据，应作为受保护 CI 产物处理。
- 配置变更自动触发校验与 plan，apply 经确定的部署授权流程执行。

## 集群到平台的引导顺序

1. IaaS 自动化创建 VM、主机基线与 K3s，完成控制面只读验证。
2. 验证 handoff 调用链，交付集群身份、API endpoint、CA 指纹及临时权限外部引用。
3. 平台仓库的外部容器化 job 核对 endpoint/CA，使用临时权限直接调用集群 API，
   安装固定版本的最小 Cilium。
4. 验证节点 Ready、Pod 网络、Service 与集群 DNS，再安装 Flux。
5. Flux 接管同一套 Cilium 安装；核对 Helm release 名称、namespace、values 和
   资源所有权，避免重复安装或两个流程同时维护。
6. 按实际依赖分别落地存储、入口、证书与可观测性，验证首次收敛。
7. 撤销临时 grant 的集群侧认证，保留 Flux 日常所需的独立访问方式。

外部 job 中运行 Helm/Cilium CLI、Flux CLI 等工具，本阶段无需常驻的外部 Flux
controllers。Flux CLI 的一次性执行与集群内 controllers 的持续运行是不同职责。
删除 secret provider 中的值不能代替临时 grant 的集群侧撤销。

## 分阶段任务与验收

以下清单全部为待办；已有部分实现应先复用核验，再按实际证据勾选。

- [ ] 1. 确定部署参数：节点规模、网络、API endpoint、存储、入口地址、域名、组件
  选型与版本。验收：配置输入明确，能够生成部署配置。
- [ ] 2. 整理仓库边界：确定公开 `iaas`、私有 `astra-ops` 与 `platform` 的真实位置
  和职责。验收：每类配置有唯一维护位置。
- [ ] 3. 打包通用实现：支持外部环境/输出目录，构建并发布版本化 OCI 镜像。
  验收：固定 digest 镜像能独立读取合成配置并执行校验、生成。
- [ ] 4. 建立 Forgejo 执行环境：部署 Forgejo、Runner、持久化与备份；验证 Git、
  镜像下载和管理网连通。验收：目标 K3s 不可用时仍能执行部署。
- [ ] 5. 建立私有流水线：固定镜像、注入非交互式凭据、配置 state/锁、校验、plan、
  授权 apply 与环境串行执行。验收：确定的配置提交驱动完整基础设施变更。
- [ ] 6. 部署 VM 和主机基线：网卡、路由、DNS、时间同步、SSH、软件源与出站策略。
  验收：节点具备安装和运行 K3s 的条件。
- [ ] 7. 部署并验证 K3s：固定版本、外部 CNI 模式、server/agent、API、etcd、角色、
  版本和服务检查。验收：控制面可用，明确保留 CNI 未初始化状态。
- [ ] 8. 修正并验证交接链路：实际入口、全量 scope、同一模型传递、CA/IP/DNS 校验、
  失败不输出与可撤销临时权限。验收：完整合成工作流通过，并验证真实集群交接输入；
  静态测试和历史 task 勾选不能替代该证据。
- [ ] 9. 引导 Cilium：确定 kube-proxy 保留或替代模式，使用真实网络参数部署最小
  Cilium。验收：节点 Ready，Pod 网络、Service 与 DNS 可用。
- [ ] 10. 安装 Flux 并接管：绑定平台仓库，声明并接管已有 Cilium release。
  验收：Flux 正常收敛，重复执行不重复安装或相互覆盖。
- [ ] 11. 部署基础平台：CSI/StorageClass、Gateway/入口地址、证书管理、基础可观测性。
  验收：按实际依赖排序，各组件完成代表性功能验证。
- [ ] 12. 完成阶段交付：临时资源验证、清理、撤销 bootstrap grant，记录重跑、升级、
  失败处理和恢复步骤。验收：基础平台可用，部署记录和维护入口齐全。

建议先实施第 1～3 阶段，再进入实际环境部署。组件依赖按选定方案细化，不能把
上述组件列表机械地当作严格串行安装顺序。

## 后置事项

- 普通业务应用和应用发布流水线：基础平台验收后另行规划。
- GitHub release 自动创建 Forgejo 版本更新 PR：先通过显式版本完成部署闭环；
  后续优先内网定时检测，只有确需即时推送时再考虑 release-bridge。
- 多环境、多租户和通用发布平台：实际需求出现后评估。
- 全面 HA、灾难恢复和性能资格：按后续运行目标确定范围。

## 关联文档

- [K3s 平台架构背景](../k3s-foundation-platform-design.md)
- [当前 K3s 操作手册](../operations/05-k3s.md)
- [外部平台所有权边界](../../platform/README.md)
- [当前 handoff 契约](../../openspec/specs/platform-gitops-handoff/spec.md)

本文是新增交付路线记录。后续实施需要同步涉及的现行契约和操作手册，尤其是
外部 CNI 的首次引导与 Flux 接管顺序。
