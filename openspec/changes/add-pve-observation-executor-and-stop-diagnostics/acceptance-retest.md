# ONE 删除兜底代码复验（2026-10-04）

用户追加授权再做一次真实测试。源码 `f3e9a57`，在 ONE 使用宿主 Docker 本地构建，
无 DinD、无 CI/OCI 发布。所有工作在 `/home/clemon/iaas-test-oesd` 内；
本轮材料位于 `retest-20261004-f3e9a57/`，构建输出使用短路径 `b3/`。

## 结果与限制

最终执行 `oesd-retest-accept-normal-20261004-03` 的 **overall 为 passed**。
full_clone、disk_boot、guest_agent、cloud_init、injected_hostname、source_unchanged 六项检查，
以及 VM、卷、snippet 清理全部 passed；residuals 为空，inventory_complete 为 true，stopping 为 null。

DELETE 仅派发一次，原生任务 stopped / OK，未触发 5 秒／15 秒存储插件兜底。
这证明最新代码在本轮环境中完成了正常全流程，**没有验证兜底重试分支的现场有效性，
也不能证明插件根因已经修复**。该分支仍依赖已有 `143 passed` 的定向软件证据。
首次测试中的 unknown、失败任务及本轮准备阶段的失败结果保持原样，不提升历史结果。

| 项目 | 实际证据 |
| --- | --- |
| 运行镜像 | 本地 image ID `sha256:5c6a5b8bfed6731854a91cce3155736da2efa6e7999a6daf2c41152dcf5647e6`，基于缓存 builder，覆盖当前源码。 |
| 镜像构建 | succeeded；实际启动后的 cloud-init、QGA 检查通过。产物 SHA256 `152b9fc6c41b995aaed8182f4678bb7db1909f70b3b0f0aa5a8d9504803d375a`，1565982720 B。 |
| 发布 | 本轮新模板 9001 发布 succeeded，导入暂存 `local`，系统盘及 cloud-init 盘 `memory`，暂存清理成功。 |
| 克隆 | cohe / `astra-pve`，池 `iaas-acceptance`，临时 VM 501，8 CPU / 8 GiB / 128 GiB；网络和身份在首次启动前注入。仅一次实际克隆。 |
| 来宾容量 | 根盘 137438953472 B、根分区 137304718848 B、文件系统 135061168128 B。 |
| 退役与清理 | 本轮模板退役 succeeded。最终 API 观察无 501/9001 及其 memory 卷，原有 500/9000 保留。只删除本轮 S3 特定版本；测试容器/镜像、临时磁盘和凭据副本已清理，原生记录保留。 |

## 准备阶段问题

- 最初复用的旧模板记录与当前 9000 的 UUID 不符，准入 `source_changed` 拒绝，未克隆。未改写旧记录或采用当前对象伪造旧 publication 归属；随后本地构建并发布本轮独立模板 9001。
- 一次构建启动缺少 scope，在启动前拒绝。补齐显式 ONE scope/runtime 后，嵌套路径使 Ansible SSH 控制套接字过长；改用同一授权目录内的 `b3` 短输出路径，独立新构建成功。未修改产品代码。
- 新模板的第一次 acceptance plan 通过，但 start 的 cloud-init 盘容量观察返回 `disk_size_unknown`，且 source snapshot 尚未建立，原执行 overall unknown；未发送任何 clone。独立观察取得 8 GiB/4 MiB 完整卷记录后，创建新 plan/admission/execution，最终完整验收通过。该容量缺测没有自动补值或在原执行中重放。
- apt 源沿用 IPv4 的 `mirrors4.tuna.tsinghua.edu.cn`。

## 证据位置

相对于 `/home/clemon/iaas-test-oesd/retest-20261004-f3e9a57/`：

- `test-summary.json`：本轮摘要；
- `outputs/publish/generated/template-record.json`；
- `outputs/accept-normal-03/diagnostics/execution/`：原 request/preview/journal/result 及来宾证据；
- `outputs/retest-retire/diagnostics/`；
- `facility-final-observation.json`、`s3-cleanup.json`、`host-cleanup.json`、`docker-*-cleanup.log`。

成功构建材料在 `/home/clemon/iaas-test-oesd/b3/work/image-tasks/oesd-retest-build-20261004-03/`。
临时 qcow2 已删除；本轮目录约 14 MiB，`b3` 约 152 KiB。此结果限定于该次真实设施执行，
未代验 infra-ops 日常部署或业务/生产资格。

## 再次复验（2026-10-04，源码 3012664）

用户再次授权，沿用同一真实路径：ONE 宿主 Docker 本地构建，无 CI、DinD 或 OCI 发布。
构建、S3 传输、PVE 发布、完整克隆、扩容至 128 GiB、首次启动、验收及模板退役均实际执行。
导入暂存使用 local，系统盘和 cloud-init 盘使用 memory；cohe、iaas-acceptance、br_dev
及网络配置沿用上一轮。调用方 plan/admission/pending/reservation 材料与互斥仍由本地测试脚本提供，
没有代验 infra-ops 集成。本轮无故障注入，未修改产品代码。

- 构建 succeeded，七项构建检查通过；运行镜像 `sha256:84c0ef4c95fe8d8f42d4c7aeff4e2670f9b374dd0937c010ad61c49171e2d15a`，复用缓存 builder 并覆盖当前源码。qcow2 SHA256 `b0633504f29211413261da361792875ef45816213895c13b8cc542f715900d9e`，1563099136 B，虚拟容量 8 GiB。
- 新模板 9001 发布成功；独立执行 `oesd-retest2-accept-normal-20261004-03` 使用 VM 501，overall passed，六项功能检查与 VM/卷/snippet 清理全部 passed，residuals 为空、inventory_complete 为 true、stopping 为 null。一次 plan/start 完成，未遇到上一轮准备阶段问题。
- DELETE 一次成功，原生 UPID `UPID:cohe:001D5C2E:104DCD3F:6AC1C640:qmdestroy:501:pve-ops@pve!opentofu:`，终态 succeeded/stopped。仍未触发 5 秒／15 秒插件兜底，不能据此提升该分支的现场证据等级。
- 模板退役 succeeded、无残留。最终 API 查询无 501/9001 及其 memory 卷，原有 500/9000 保留。本轮 S3 特定版本、四个测试容器、本地运行镜像、临时磁盘和凭据副本均已清理，原生证据保留。

本轮材料：`/home/clemon/iaas-test-oesd/retest2-3012664/`，摘要 `test-summary.json`，
验收原件 `outputs/accept-normal-03/diagnostics/execution/`，最终查询及清理回执
`facility-final-observation.json`、`s3-cleanup.json`、`host-cleanup.json`。
构建材料使用短路径 `/home/clemon/iaas-test-oesd/b4/work/image-tasks/oesd-retest2-build-20261004/`，
临时 qcow2 已删除。软件源继续使用 `mirrors4.tuna.tsinghua.edu.cn`。
