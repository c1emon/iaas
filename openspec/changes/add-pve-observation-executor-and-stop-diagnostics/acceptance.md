# ONE 限定真实验收（2026-10-04）

用户授权在 ONE 本地构建、使用宿主 Docker（无 DinD、无 CI 发布），工作目录仅
`/home/clemon/iaas-test-oesd`；最多两次顺序克隆，并清理本次资源。
实际目标为 `astra-pve` / cohe，验收池 `iaas-acceptance`，新模板 9001、临时 VM 501。
原有 500、9000 被占用，未用于本次写操作。导入暂存为 `local`，系统盘及 cloud-init 盘为 `memory`。

## 结果

| 路径 | 实际结果 |
| --- | --- |
| 镜像构建及独立启动 | 构建成功；独立镜像测试成功，cloud-init/QGA 启动检查完成，base_unchanged 为 true，清理无残留。 |
| 发布 | 9001 发布成功，local 暂存清理成功。首次下载因 S3 签名 region 错误而失败且未写 PVE；修正为既有 `cn-sh-loc` 后使用新独立执行成功。 |
| 正常克隆 | 六项检查全部 passed：full_clone、disk_boot、guest_agent、cloud_init、injected_hostname、source_unchanged。8 CPU / 8 GiB / 128 GiB，首次启动前注入网络与身份；来宾根盘 137438953472 B、分区 137304718848 B、文件系统 135061168128 B。 |
| 常规清理 | DELETE 原生任务 stopped / `unexpected status`，日志仅有 `TrueNAS [INFO] : Ping`；整体保留 unknown，不声称完成一次含常规清理的完整成功验收。与先前记录相似，当前日志不足以确认更具体的插件根因。 |
| 正常克隆独立恢复 | 新只读 preview、限定 admission、互斥锁下执行；overall/cleanup passed，VM、两卷及专属 snippet absent，residuals 为空。 |
| 登记前停止 | 第二次克隆完成候选 UUID、marker、slots/content 证据后，在 ownership 登记前注入 UnknownOutcome；未启动来宾。原执行 unknown；新 pre_registration preview 证明关联，独立恢复 overall/cleanup passed、residuals 为空。 |
| 退役及最终观察 | 本次模板 9001 退役 succeeded；最终 API 观察无 501/9001 及其 memory 卷，原有 500/9000 仍在。仅删除本次 S3 object VersionId；测试容器、本地镜像标签、临时 qcow2/guestfs cache、凭据和运行时私钥副本已清理。原生 JSON/日志保留，ONE 目录约 14 MiB。 |

ONE 的 apt 镜像源使用 `mirrors4.tuna.tsinghua.edu.cn`，避开已观察到的 TUNA IPv6 403。
未修改 ONE 全局 IPv6/DNS 设置。

## 固定材料与修复

- 构建源码基线：`0a4c582`；本地运行镜像 ID：`sha256:eba6bb8b402ee874ad094c924260b780f3533aa37f90904fe179a5881bbe7020`。
- 构建产物 SHA256：`bcf3733c29d8a9b0474336b44c44de1b910877149472230373d4bb5f0a2858b4`，1565982720 B，虚拟容量 8 GiB。临时磁盘已删除，artifact/build-result 记录保留。
- 测试发现并修复：来宾执行已成功而 VM 停止后 QGA 不可查询，恢复可使用绑定原 journal 的 terminal success；live running 仍优先，缺 PID／unknown／failed 不新增此豁免。工作全通过但清理失败时，stop_diagnostics 记录 cleanup 停止点。
- 修复镜像 ID：`sha256:eccc7cabaec0b683798014ce8e205a50764f04823d87ebd7498a2944a2addede`；该版本完成两次独立恢复、第二次停止测试和模板退役。首次正常克隆的原始结果不重写。清理停止点修复由定向软件测试覆盖，本次未再触发第三次真实克隆来复验该展示分支。
- 修复相关六个测试文件共 `128 passed`；改动源文件 Ruff、Pyright、diff 检查通过。GitNexus impact 已执行，diagnostics 为 CRITICAL；`_task_activity` 刷新索引后仍 UNKNOWN，以直接调用点及定向测试补足。detect-changes 的图统计不作为动态调用无影响证明。

原始证据均在 ONE 上述目录：

- `outputs/build/work/image-tasks/oesd-build-20261004/`、`outputs/image-test-02/`；
- `outputs/publish-02/generated/template-record.json`；
- `outputs/accept-normal/diagnostics/execution/`、`outputs/accept-pre-registration/diagnostics/execution/`；
- `outputs/recovery-normal-03/work/pve-recovery/`、`outputs/recovery-pre-registration-02/work/pve-recovery/`；
- `outputs/retire-05/diagnostics/`；
- `facility-final-observation.json`、`s3-cleanup.json`、`host-cleanup.json`、`docker-*-cleanup.log`。

此次为限定真实设施测试，没有发布 OCI 版本、运行 CI/匿名消费校验，也未代验
infra-ops 日常部署或业务/生产资格。常规 DELETE 失败仍为未通过项，独立恢复成功不提升原验收结论。
