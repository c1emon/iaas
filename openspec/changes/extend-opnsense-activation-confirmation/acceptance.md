# 实施与软件验证记录

状态：部分交付，剩余任务受下述原生能力缺口阻断，尚未完成全部任务。目标为固定 Collection
`1423500c29f88da9ba8147a23fc64006cf464159` 和 OPNsense `26.7.3`。
实现分支：`feat/extend-opnsense-activation-confirmation`。
未访问设备、增加现场权限、发布镜像、创建 PR 或合并。

## 已实现的公共路径

- candidate/result/recovery v2，request 与 launcher interface v1；旧候选明确要求重新 plan。
  v1 recovery 仅依赖实际 before、已核清 after 和当前现场一致性生成新的配置逆向候选。
- 各阶段绑定确认条件、配置派生内容动作和等待预算；plan 保存 blocked 候选并非零退出。
  apply 在首写前检查所有阶段，再在阶段边界复核；后阶段能力缺口不会留下前阶段写入。
- 不用活动成员匹配提升本次 activation。content_update 按身份、候选来源及加载证据分别判定；
  当前 verify 独立汇总，不更改原 apply 结果。
- 只对 processing/accepted/unconfirmed 且有可关联只读观察的动作进行有界等待。固定 API 当前无已准入的
  异步完成端点；该等待路径使用可控时钟和合成观察验证，不宣称设备已支持。
- 静态 host/network/networkgroup 按完整 IPv4/IPv6 地址集合比较，依赖使用必要现场值；
  不完整、动态、重复依赖不会按空集成功，不扩大写入集合。
- port Alias 从固定 API 保存规则与已加载 PF 规则按 UUID 关联，定向解析协议、
  源/目标端口和范围。无法表达的翻译端口或语法明确返回不完整，不冒充无消费者。

## 尚未解除的能力边界

完整源码依据见 [capability-notes.md](capability-notes.md)。

- Alias/Gateway/Group 的原生返回会丢弃必要子动作的失败，缺少足够的本次完成证据。
  即使当前状态匹配，受影响写入仍 blocked；Filter/NAT/VIP 保留已核定同步返回路径。
- 动态 Alias 缺少逐来源处理、缓存归属/有效期和加载证明；当前不允许缓存复用，不能把
  未实现的允许缓存/过期重检分支视为完成。原生恢复无法确认时返回 manual_required，
  可另行授权人工处理或使用已核清材料显式计划配置逆向；不伪造差异或循环要求 plan。
- 禁用/删除的空 table 响应可能掩盖后端读取失败；表残留及配置不存在分别报告，
  不据此声明完整退役，不清 PF state。
- DNAT/1:1 NAT 原生加载规则缺少与保存配置 UUID 的稳定关联；相关 port/group
  消费者返回明确能力缺口，不按无消费者成功。Filter 的 UUID 关联检查已实现。
- 接口组当前成员可用内核 `ifconfig` groups 与逻辑/物理接口映射核对；该快照不能证明
  本次注册或 filter reload 已完成，也不能单独证明相关规则已消费新成员。

## 验证边界

软件验证覆盖工作流、读取适配、固定 Ansible writer、runtime 文件选择和凭据隔离。
既有 launcher Go 测试覆盖 local/DinD 文件映射与恢复交接，未将测试替身或可用的本地
Docker daemon 表述为实际 DinD 容器执行，更不构成 OPNsense 设备/业务验收。

## AC 覆盖

| 条目 | 本轮实现与软件证据 | 保留边界 |
| --- | --- | --- |
| AC-01 | v2 确认合同、blocked 计划落盘、所有阶段首写前复核；末阶段缺口零写入 | 允许缓存复用的证据规则尚不可用；2.1/2.2 保留未完成 |
| AC-02 | 可控时钟验证延迟、失败、取消、次数/阶段/单请求预算；等待只读且不重放写入 | 当前固定 API 没有已准入的异步完成端点，不宣称现场异步支持 |
| AC-03 | Filter PF 端口展开检查及原生读取接线；协议、角色、范围、无消费者、不可读反例 | NAT 消费者缺稳定身份关联，4.2 保留未完成；未知语法不成功，不证明本次 reload |
| AC-04 | 静态 networkgroup、必要现场依赖及地址集合语义测试 | 动态或不完整依赖不作空集 |
| AC-05 | 配置派生初始化/更新、无描述强刷、来源绑定、批内失败及 manual_required | 来源处理、有效缓存和逐对象加载证明缺口；4.4 未完成 |
| AC-06 | 配置/活动表分离，缺表、空/不可读、残留观察；不清 PF state | 不能证明完整原生退役；4.5 未完成 |
| AC-07 | 当前 Gateway 配置、按用途路由和相关 PF 消费者观察 | 原生 routes configure 结果未传回；5.1 未完成 |
| AC-08 | 逻辑/物理映射、内核组成员与 PF 消费者分别核对 | 本次注册/filter reload 完成证据缺失；5.2 未完成 |
| AC-09 | v2 分立版本、旧候选拒绝、旧恢复材料受限读取；verify 不追认历史结果 | 当前状态与本次完成分开；静态 Alias 也不据此放行写入，4.1 未完成 |
| AC-10 | 共享激活准入、漂移/冲突停止、部分保存后停止和私有输出/恢复回归 | 软件证据不替代调用方现场串行化或业务验收 |

## 本轮验证结果（2026-09-20）

- 受影响 Python workflow/reader/writer/contracts、确认与资源检查、Ansible 入口、runtime
  分发及凭据隔离：**268 passed**。
- `uv run pyright automation/src/iaas_automation/opnsense_workflow`：0 errors。
- `automation/launcher` 下 `go test ./...`：通过；含既有 local/DinD 文件映射及失败恢复
  的替身测试，不是启动真实 DinD 容器或执行真实 OPNsense 的证明。
- 在独立临时 `ANSIBLE_HOME`、项目 `ansible.cfg` 和项目固定 Collection 路径下运行
  `uv run ansible-lint automation/ansible/playbooks/opnsense`：23 files，0 failures，0 warnings。
- 五个 v2 JSON 示例解析通过；候选摘要、旧版本拒绝和恢复限制由合同测试覆盖。
- `openspec validate extend-opnsense-activation-confirmation --strict`、`git diff --check`
  和提交前 GitNexus `detect_changes(scope=all)` 均作为提交门禁；图分析单独记录完整性。
- 代码阶段图变更检查：243/243 个变更符号、31 条受影响流程，risk=critical，返回中无
  `partial=true`/`truncated=true`。仓库全局流程枚举有预算上限；未列出的流程不被当作
  无影响依据，动态调用通过实际调用点与定向测试补充核对。

未完成的任务保留未勾选，不创建 PR、不归档，不将上述软件测试写成设备验收。
