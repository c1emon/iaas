# 实施与验证

- 实现：固定 transport 的可嵌套观察预算；Reader 配置/主动观察及关联完成轮询入口开启作用域。executor、HTTP helper、diagnostics 和恢复准入未改动。
- 离线：原有 OPNsense 集合 598 项、共享 HTTP 21 项、新观察字节回归 7 项通过；Pyright 零错误，新改测试 Ruff 通过。
- 缺陷复现：将旧 main reader 加载到隔离 Python 进程，重复读取与超限后新一轮读取两项新测试均按预期失败；修复实现通过。未改动工作树来切换旧源码。
- 执行覆盖：真实 Reader 与固定 transport 配合假 HTTP 响应完成两阶段 apply；注入超限后执行停止，新恢复回读可以确认后态；持续读取失败保持 unknown。轮内累计超限、响应关闭、嵌套字节预算及共享时间 deadline 仍受测试约束。
- Luna/high 独立复核未发现生产入口遗漏或轮内限制放宽。底层直接调用保留原累计行为，非固定注入 transport 不声称获得新增 HTTP 保护。
- 设备写入：用户授权新测试窗口并确认 GUI 无待应用配置、其他写入暂停后，使用本地源码提交 `9d67d28` 实测；不是 rc.10 镜像验收，原始 rc.10 失败及 unknown 记录不改写。

## 2026-09-21 设备结果

**观察预算修复获得实机验证；完整 apply / 原生恢复闭环仍被 Filter 激活失败阻断。**

- 初始独立 read：7 类资源完整。Alias 12/26、Gateway 1/3、Interface Group 0/3 可表达，范围未扩展。
- 创建候选：仅新增未被规则引用的 `IAAS_BUDGET_TEST_9B2190`（192.0.2.253）和禁用 Filter `iaas:opnsense:filter:budget-test:disabled-9b2190`；两者初始均不存在，测试规则不引用 Alias。
- 创建 apply：Alias 保存、激活、配置回读成功；Filter 保存及配置回读成功，但原生 `firewall/filter/apply` 激活失败，整体结果 failed。
- 同一 reader 完成 14 轮观察，累计 19,057,349 字节，最大单轮 1,942,715 字节，全部 complete。该逐轮计数来自本轮私有包装器，不用于推断 rc.10 原始调用轨迹。
- 失败后的原生 recovery 中，两条记录均 attempted、expressible、after_status=confirmed。直接通过 `plan --recovery` 生成仅删除这两个对象的新候选，未重写历史恢复材料或手工构造替代删除声明。
- 恢复 apply：两个对象删除保存并回读成功，Alias 激活成功，Filter 激活再次失败，整体仍 failed；14 轮观察累计 19,205,254 字节且全部 complete。
- 最终独立 read：两个测试对象均不存在，7 类资源的可观察身份、配置、引用和恢复标记与测试前一致。恢复候选独立 verify 为 fully_verified，仅证明保存配置，不证明激活完成。

Filter 激活的 no_log 任务仅保留 failed/unknown，临时脱敏 callback 也未取得足以分类的原因；现有证据不能区分设备拒绝、传输失败与不符合成功合同的响应。固定 Collection 原生 rule reload 使用相同的 POST 路径，未发现目标参数错配。后续最小工作是补充安全失败分类，再验证该路径，不能通过放宽成功判断绕过。

未执行客户端业务验证；不可表达对象的原生字段、PF/数据面及 GUI 待应用状态未由最终配置比较证明。测试对象配置已清理，但不声称 Filter 共享激活已完成。私有候选、原生恢复、逐轮计数和最终比较保留在 `/private/tmp/iaas-observation-live-n7knb04k/`，未提交设备原始数据。
