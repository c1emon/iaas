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

## Filter 激活失败根因补查

用户随后要求定位具体原因。保留 no_log 和原成功判断，仅在受保护失败结果中增加状态分类、长度、HTTP 状态码和超时标记；不保存 backend message、请求或凭据。27 项 writer/Ansible 测试通过，包括实际渲染含秘密标记的合成错误，确认结果不泄露原文。

使用新的 activation_recovery 候选（仅已删除的测试 Filter，零配置改动）执行一次诊断。首次 1Password 授权超时发生在 workflow 启动前；授权重试后才产生激活请求。设备结果为 response_present=true、response_status_class=ok_with_whitespace、response_status_length=4、timeout_reported=false；当前 gate 仍返回 failed，配置回读 verified，恢复后态 confirmed 且对象不存在。

**根因是成功状态字符串尾部的两个换行未归一化，导致 IaaS 误报失败。** OPNsense 26.7.3 的 [script action](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/service/modules/actions/script.py#L28-L41) 成功返回 `OK`，[process handler](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/service/modules/processhandler.py#L169-L186) 追加 `\n\n`；[Backend](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/library/OPNsense/Core/Backend.php#L137-L170) 仅去掉 NUL 结束符，[Filter apply](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/FilterBaseController.php#L280-L287) 原样返回。该 `OK\n\n` 与实测长度及分类一致，当前 `string | lower != 'ok'` 必然拒绝它。

本阶段定位根因并保留安全诊断，尚未修改成功判定。后续修复应在原生响应边界裁剪外围空白后仍精确比较 `ok`，不接受任意非空响应；Python writer 消费该任务明确的 confirmed/failed 状态，无需放宽其状态合同。原生 wrapper 成功与 PF/客户端业务验收继续区分；历史失败产物不追改为成功。

## 外部响应状态统一修复与补测

共享 Pydantic 转换严格接受非空字符串，去外围空白并转小写；Ansible filter 与 Python 复用同一实现。接入 OPNsense 共享激活、独立 Interface Group、K3s readyz，以及 PVE 节点、存储、VM、HA、Ceph 的外部状态判断。内部状态机及声明不放宽，每个调用点保留自身状态枚举。带空白的 PVE inactive / failed 不再漏过失败判断。

定向转换、PVE health、实际 Ansible writer、OPNsense 入口和 K3s 测试共 76 项通过，类型检查通过。PVE/K3s 未做联机测试。

同一已确认设备窗口内，基于最终源码重新生成零配置改动的 Filter activation_recovery 候选并执行一次：save=unchanged、activation=confirmed（native_response）、configuration=verified、整体 fully_verified。已删除测试 Filter 仍不存在，先前清理的激活阻断解除；历史创建/恢复失败产物不改写。本轮未执行 PF 或客户端业务验收。私有材料位于原临时目录的 activation-unified-plan / activation-unified-apply。
