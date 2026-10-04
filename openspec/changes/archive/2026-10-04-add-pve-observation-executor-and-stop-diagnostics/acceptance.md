# ONE 首次真实验收（2026-10-04）

首次正常验收 **overall unknown**：六项功能检查 passed，但 DELETE 任务 stopped / `unexpected status`。
两次独立恢复通过，最终资源已清理；恢复成功不提升原验收结论。
后续两轮完整通过，见 [复验记录](acceptance-retest.md)。

## 覆盖与结果

ONE 宿主 Docker 本地构建，无 DinD、CI 或 OCI 发布。目标 `astra-pve` / cohe，
池 `iaas-acceptance`；新模板 9001、临时 VM 501，8 CPU / 8 GiB / 128 GiB。
导入暂存 local，系统盘和 cloud-init 盘 memory；原有 500/9000 保留。

| 路径 | 结果 |
| --- | --- |
| 构建、独立启动及发布 | 成功；cloud-init/QGA 检查通过，基础镜像不变，local 暂存已清理。 |
| 正常克隆验收 | full_clone、disk_boot、guest_agent、cloud_init、injected_hostname、source_unchanged 全部 passed。 |
| 常规清理 | DELETE 失败，日志仅有 TrueNAS Ping，根因未确认；原执行 unknown。 |
| 独立恢复 | 正常克隆恢复 passed；另一次克隆在登记前注入 UnknownOutcome，原执行 unknown、独立恢复 passed。 |
| 退役与清理 | 模板退役成功，VM/卷/snippet 无残留；本次 S3 版本、容器、镜像、临时磁盘和凭据已清理。 |

测试促成 `5ed58a2` 修复：保留已成功的来宾执行证据供恢复使用，并在清理失败时记录停止点。
定向软件测试 `128 passed`。本次限定设施证据不覆盖 infra-ops 集成或生产资格。

## 证据

ONE 根目录 `/home/clemon/iaas-test-oesd/` 保留原生 JSON/日志：

- 构建与启动：`outputs/build/`、`outputs/image-test-02/`；发布：`outputs/publish-02/`。
- 验收：`outputs/accept-normal/`、`outputs/accept-pre-registration/`。
- 恢复：`outputs/recovery-normal-03/`、`outputs/recovery-pre-registration-02/`；退役：`outputs/retire-05/`。
- 清理回执：`facility-final-observation.json`、`s3-cleanup.json`、`host-cleanup.json`。
