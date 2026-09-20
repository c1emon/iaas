# 实施与软件验证记录

状态：按本轮用户确认的修订范围完成软件实现与验证，任务全部勾选。默认流程以保存、配置回读和原生激活成功为基础；Alias/Gateway/Group 的深度能力缺口固定记录为不可关闭警告，不阻断默认流程。源码基线为固定 Collection
`1423500c29f88da9ba8147a23fc64006cf464159` 和 OPNsense `26.7.3`。
实现分支：`feat/extend-opnsense-activation-confirmation`。
未访问设备、增加现场权限、发布镜像、创建 PR 或合并。

## 已实现的公共路径

- candidate/result/recovery v2，request 与 launcher interface v1；旧候选明确要求重新 plan。
  v1 recovery 仅依赖实际 before、已核清 after 和当前现场一致性生成新的配置逆向候选。
- 各阶段绑定保存/回读/原生激活条件与警告；plan/apply 保留候选绑定、漂移、引用完整性和凭据保护。
  核心条件失败时首写前阻断；Alias/Gateway/Group 深度缺口以固定 stderr 警告和 result 记录并继续。
- 不用活动成员匹配提升本次 activation。默认结果分离保存、配置回读、原生激活和深度警告；
  当前 verify 独立汇总，不更改原 apply 结果。
- 默认不等待或轮询深度状态；原生激活响应和配置回读分别记录，深度观察由独立 inspect 触发。
- 静态 host/network/networkgroup、port、Gateway、接口组和 runtime 深度核对移入可选 inspect；
  默认不扩大写入集合，警告和未覆盖范围保留在 result。
- 动态 Alias 遵循设备原生缓存刷新；不要求来源、缓存归属/有效期或逐对象加载专用证据。

## 可选深度核查与保留边界

完整源码依据见 [capability-notes.md](capability-notes.md)。

- Alias/Gateway/Group 的原生返回缺少部分深度子动作事实；默认流程固定输出不可关闭 stderr
  警告并在 result 记录，继续保存/回读/原生激活。需要深度事实时使用独立 inspect，
  不把 inspect 未执行伪称为已验证。
- 动态 Alias 遵循设备原生缓存刷新；不新增来源、缓存归属/有效期或逐对象加载证明要求。
  恢复仍需核清后态、候选绑定、漂移、引用完整性和凭据保护。
- 禁用/删除的空 table 响应可能掩盖后端读取失败；表残留及配置不存在分别报告，
  不据此声明完整退役，不清 PF state。
- DNAT/1:1 NAT 原生加载规则缺少与保存配置 UUID 的稳定关联；相关 port/group
  消费者返回明确能力缺口，不按无消费者成功。Filter 的 UUID 关联检查已实现。
- 接口组当前成员可用内核 `ifconfig` groups 与逻辑/物理接口映射核对；该深度检查由 inspect
  可选执行，不能改变默认原生激活结果，也不能单独证明相关规则已消费新成员。

## 严格项审计结果

固定 26.7.3 源码和只读端点已核定 PF 规则、Gateway 路由/运行字段、接口组映射和 runtime
相关事实；这些事实不纳入默认 plan/apply/verify。默认成功只依赖保存、配置回读和原生激活成功。
Alias/Gateway/Group 的缺口通过不可关闭 stderr 警告及 result 字段保留。需要协议/端口、
route-to、接口组成员或 runtime 深度事实时，使用独立 inspect：
`PYTHONPATH=automation/src uv run python -m iaas_automation.opnsense_workflow.inspect --inventory INVENTORY --candidate CANDIDATE --output OUTPUT`。
inspect 只读当前状态，不证明内部子动作或业务验收。本段不把软件测试替身或源码能力写成设备验收。

## 验证边界

软件验证覆盖工作流、读取适配、固定 Ansible writer、runtime 文件选择和凭据隔离。
既有 launcher Go 测试覆盖 local/DinD 文件映射与恢复交接，未将测试替身或可用的本地
Docker daemon 表述为实际 DinD 容器执行，更不构成 OPNsense 设备/业务验收。

## AC 覆盖

| 条目 | 本轮实现与软件证据 | 保留边界 |
| --- | --- | --- |
| AC-01 | v2 确认合同、候选绑定、漂移/引用/凭据保护和核心首写前复核 | Alias/Gateway/Group 深度缺口改为不可关闭警告，不阻断默认流程 |
| AC-02 | 原生激活响应、配置回读和失败/unknown 分离 | 深度 PF/group/runtime 检查不在默认流程 |
| AC-03 | PF 端口展开属于独立可选 inspect 范围 | 不在默认 plan/apply/verify 调用，inspect 输出独立报告 |
| AC-04 | 静态 networkgroup、必要现场依赖及地址集合语义测试 | 动态或不完整依赖不作空集 |
| AC-05 | 配置派生动作保留候选绑定、无描述强刷和原生激活语义 | 动态内容遵循设备原生缓存刷新，不要求来源/缓存/加载专用证据 |
| AC-06 | 配置/活动表分离，缺表、空/不可读、残留观察；不清 PF state | 退役深度观察由 inspect 可选执行；缺口 warning/result 不阻断默认保存/回读/激活 |
| AC-07 | 默认 Gateway 保存、配置回读和原生激活；深度路由/consumer/monitor 可由 inspect 补充 | 原生返回缺口固定警告并记录，不阻断默认流程 |
| AC-08 | 默认接口组保存、配置回读和原生激活；当前成员/规则接口观察可由 inspect 补充 | 不把可选观察表述为 registration/filter reload 完成证明；缺口作为不可关闭警告保留 |
| AC-09 | v2 分立版本、旧候选拒绝、旧恢复材料受限读取；verify 不追认历史结果 | 当前默认结果与可选深度 inspect 分开 |
| AC-10 | 共享激活准入、漂移/冲突停止、部分保存后停止和私有输出/恢复回归 | 软件证据不替代调用方现场串行化或业务验收 |

## 本轮验证结果（2026-09-20）

- OPNsense Python、Ansible 回归及 runtime dispatch：570 passed；随后新增的旧策略候选拒绝、可选版本探测和显式内容失败边界经聚焦套件验证：64 passed（与前者有重叠，不累加）。
- workflow 全模块 pyright：0 errors、0 warnings。
- OPNsense playbooks ansible-lint：23 files，0 failures、0 warnings，使用隔离的本地 Ansible 目录。
- 严格 OpenSpec 校验和 `git diff --check` 通过；提交前 GitNexus `detect_changes(scope=all)` 完整，无 partial/truncated。共享合同影响评级为 CRITICAL，已核对 plan/apply/verify、runtime、writer 和恢复路径并覆盖相应软件回归。
- 合成 candidate/result/recovery/reverse-candidate 已按新合同重新生成，两份候选均通过读取校验，逆向恢复声明生成通过；删除了已不符合默认策略的 blocked 示例。
- 沿用本分支此前已通过的 launcher local/DinD 模拟回归；本轮未修改 launcher。所有测试替身、源码核对和可选 inspect 均不构成设备或业务验收。

上游内部子步骤反馈及 NAT 深度关联限制作为非阻断保留项；没有新增 SSH、插件、权限或设备操作。本轮不创建 PR、不归档、不发布。
