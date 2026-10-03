# Proposal

## Why

PVE 原生任务结束后，配置、资源池和存储清单可能尚未同步；当前若干检查立即失败，部分任务／来宾只读查询的短暂失败也会提前结束观察。归属登记前停止时缺少可安全恢复的证据，结果又不足以直接解释失败检查、任务活动及残留；镜像执行器尚未检查可用内存和容器限制。

## What Changes

- 统一一个有限的观察等待执行器，覆盖任务完成、状态收敛和允许的只读查询重试；复用绝对截止时间，写操作只派发一次。
- 覆盖镜像／依赖传输、导入／克隆／模板转换、克隆归属、配置／容量、QGA／cloud-init／来宾配置、删除后消失和 snippet 文件／引用核验。
- 在失败判定前按阶段／检查／资源保存必要预期／实际字段、查询时间及原因，包括卷的 `volid/vmid`；后续检查不覆盖失败证据，输出可消费的停止诊断。
- 对“克隆成功、归属确认未完成、journal 未登记完整资源”提供限定恢复：原 clone 请求携带 preview 绑定的一次性非凭据关联标记，先保存候选 UUID／完整挂载卷集合，再独立核验归属，冻结范围后另行批准清理；缺少这组关联材料的早停拒绝认领。
- 镜像 build/test 保留简单内存预检：读取宿主及当前容器可直接观测的余量，已知不足拒绝，读不到仅记录 unknown；不增加全 cgroup 布局或祖先完备性门禁。
- 普通 post-apply 验证组和独立 verify 在各自入口用已有 timeout 或有限内部默认值冻结一次观察截止，查询／重试共用；不增加 apply 必填审批字段，既有明确截止只取更紧值。
- **BREAKING**：仅对字段或语义实际变化的当前 request/preview/admission/journal/result/schema 更新必要版本，发布操作补齐执行绑定的截止时间。离线 check 拒绝缺失或不支持的参数。不增加旧版本启动兼容；原始历史证据保持不变。

## Capabilities

### New Capabilities

- `bounded-observation-executor`：只读观察、状态分类、非延长预算和必要证据的统一执行语义。

### Modified Capabilities

- `pve-template-lifecycle`：发布／清理／退役的任务和目标状态观察，共享绑定截止时间。
- `pve-template-acceptance`：归属、配置、容量、来宾和清理的状态收敛，候选资源证据。
- `pve-acceptance-recovery`：登记前停止的独立证明及限定恢复，恢复任务和消失检查。
- `pve-snippet-cleanup`：上传／删除后文件与引用的只读核验，不重放 helper 写操作。
- `image-build-tool`：简单 build/test 内存观察和固定镜像传输的有限重试。
- `pve-execution-results`：普通 PVE 部署的计划绑定收敛检查、必要判定证据和原生停止诊断。
- `runtime-environment-config`：受影响当前输入的离线合同与能力检查。

## Impact

影响 `src/iaas/pve_template/`、PVE 配置验证／结果、snippet runtime/helper、image runtime 和固定依赖准备路径，以及相关 schema、CLI 能力声明、测试和文档。复用现有 `DeadlineBudget` 与已准入的单次传输；不让底层 HTTP transport 自动重试。OpenTofu/provider 自有设施操作仍由原执行路径派发，不包装成可重试 apply。

最小充分的软件实施预计 **M（2–5 天）**：一个观察组件、上述域适配、当前合同／诊断、内存预检及代表性正反例。原生存储同步和任务关联不能由替身测试证明；如后续另行授权，可增加 **S（≤1 天）** 的专用池真实验收，最多两次顺序临时克隆，用于主线与登记前停止／恢复；固定版本发布也留待实施授权。后续维护按变化的检查点补定向测试，复用既有 CI／发布校验，不建立逐对象证据或版本矩阵。后置真实验收不阻断软件交付，但结论只能是软件验证。

本 change 当前仅规划。外部存储插件的 `unexpected status` 如实返回，不修复插件、不自动补偿或重复删除。infra-ops 继续负责正式清单、凭据、权限、审批、日常 apply、待处理结算和业务验收；本仓库只提供接口及适配说明。
