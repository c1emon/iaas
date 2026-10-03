# 调用方适配清单

本 change 交付 IaaS 软件实现；本次未发布新 OCI 版本，未执行真实 PVE 验收，也未修改 infra-ops。

| 接口 | 当前调用方要求 |
| --- | --- |
| publication | 使用 publish request v3、cleanup/retire request v2、preview/result v4；request 和 admission 绑定同一 work/cleanup UTC 截止，preview digest 绑定完整输入。template record 仍为 v3。保存原生 journal/result 和分组观察证据。 |
| acceptance | 使用 preview v2、result v4；plan 生成一次性 clone marker 并绑定批准，调用方不自填或补写 marker。候选 UUID/完整槽位卷快照不代表 owned。 |
| recovery | 使用当前 recovery preview/result v2，重新取得有限 one-shot 批准。传递原 request/preview/admission/journal/result、caller pending/consumption 和必要前次恢复材料；缺原 UPID/marker/完整候选时按 needs_evidence 处理。先只读 plan，按冻结 scope 执行 exact cleanup；不修改原材料。 |
| saved-plan verify | 沿用既有 admission；无需新增必填观察截止或批准字段。post-apply 与独立 verify 各冻结一次适用 timeout 或默认 120 秒的只读窗口。独立 verify 不沿用已结束原窗口，也不证明历史 apply 成功。 |
| snippet | 更新对应 helper，再消费 exact-file/digest/inode 与完整引用证据；响应丢失保持活动未知，不重发 upload/delete。普通上传的 verify 使用 upload helper 的只读 observe 模式。 |
| 停止诊断 | 消费 `stop_diagnostics` 的完成/停止检查、任务活动、归属/存在性、清单完整性和恢复所需材料；整体 unknown 与已知 failed 检查可并存。不得以当前 VMID/marker 认领资源。 |
| image build/test | 执行器记录宿主和当前容器直接可读内存余量；已测不足拒绝派发，缺测量 unknown 单独不阻断。离线 check 不使用规划机内存推断执行器容量。 |

离线 check 只证明当前输入格式与能力声明有效；定向软件测试只证明覆盖的替身/本地路径。
固定 OCI 发布及匿名消费、限定真实克隆/来宾/恢复/清理、infra-ops 日常部署各自需要其对应证据。
已知外部 storage 插件故障不会被只读重试改写为成功。

真实验收仍按原提案的后续授权范围承接：复用专用池/源模板，最多两次顺序临时克隆，预计 S（≤1 天）。
此次没有该设施授权，未创建或删除真实临时资源；该延后项不阻断软件交付，但真实同步行为、来宾扩容与现场恢复仍未验收。
