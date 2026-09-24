# 切换到独立镜像工具与 HTTPS 模板发布

本步骤用于已有节点 helper 的站点切换。新版软件不解析旧 preview/receipt，也不提供旧构建入口或 force 回退。原始记录仍须保留，已有模板可以重新读取当前事实后登记；没有证据的构建历史保持未知。

字段与入口见 [合同](../contracts/image-publish-v1.md)，站点负责执行窗口、任务串行化及可用模板名单。此文档和软件升级本身不执行节点卸载或创建资源。

## 停止旧任务准入并完成在途任务

先在调用方停用旧模板构建及清理任务的提交入口，保留已有任务的观察与结果收集。不要通过删除 helper、撤销正在使用的凭据或强杀 worker 来完成 drain。

已知旧实现风险：`f98e5f9` 的 helper 对锁文件父目录无条件执行 `chmod(0700)`，其默认节点锁位于共享 `/run/lock`；已在 cohe 导致 pveproxy 锁文件访问失败。不要为了迁移检查而新调用这条旧加锁路径。目录权限修复不消除仍安装的旧代码，切换须实际停用旧准入并移除旧入口；新版只管理自己的私有任务目录权限。

在目标节点检查仍被 systemd 管理的旧任务：

```sh
sudo systemctl list-units --all 'iaas-pve-template-*.service'
```

对调用方 pending 和 `/var/lib/iaas/pve-template/executions/` 中尚未核清的执行，按原记录的确切 unit 名检查 `ActiveState`、`SubState`、`MainPID`、`ControlGroup`、`Result` 及已保留的退出信息。活动任务应等待其结束；失去 unit 或连接不表示执行成功，也不表示可以删除其对象。

旧原始结果完整时，用调用方原有核清流程登记。结果缺失、对象归属不明或仍有副作用时，保留 pending 和材料，按明确的对象与所属管理方恢复。已纳入 OpenTofu 的对象由所属完整 root 处理，不能交由模板 helper 删除。无法核清的执行不转写成新版成功记录，也不为了切换重放旧写入。

## 保留原始证据与移除旧入口

确认无活动旧 worker、相关 pending 已核清或明确交接后，保存原始 execution 目录、私有 worker 日志、原调用方请求/preview/result 以及对应软件版本。原默认路径是 `/var/lib/iaas/pve-template`；若原安装显式设置了其他根目录，以实际安装记录为准。

使用站点现有私有备份渠道保存目录，不输出原始日志或凭据。无需另建逐文件签名系统。保留原目录直到站点既定保留期和恢复依赖允许删除；卸载 helper 不删除这个目录。若需留存旧二进制供人工调查，应移到受控证据目录，不能保留可被 CI/sudo 调用的第二执行入口。

在已批准的节点切换范围内，移除以下确切文件：

```sh
sudo rm -f -- /etc/sudoers.d/iaas-pve-template \
  /usr/local/sbin/iaas-pve-template \
  /usr/local/sbin/iaas-pve-template-worker \
  /usr/local/sbin/iaas-pve-storage-status \
  /usr/local/sbin/iaas-pve-template-build
sudo visudo -c
```

若曾使用其他确切旧安装路径，先核对其来源再单独移除，不按名称通配删除文件。保留 `iaas-pve-snippet-upload` 及其 sudoers；它仍服务于独立的 VM/snippet 路径。不要删除 `pve-ops` 身份、其仍被使用的 SSH 信任或 PVE 自身的 `qm`、`pvesh`、QEMU、Python/systemd 包。

新版节点 bootstrap 不再为模板加工安装 libguestfs 工具。已安装节点上，只有确认 libguestfs 工具由旧模板构建引入且没有其他使用者后才移除对应包；不要运行无范围的 autoremove。Packer、Ansible 与离线镜像工具由独立 image-builder runtime 提供。

## 启用新合同

先固定同一发布版的 launcher、普通 runtime、image-builder runtime 和合同/schema，再接入以下两段流程：

1. 在专用 Linux amd64/KVM 执行器上直接运行 image build/test/clean，保留原任务目录与结果；检查、读取和被动验证不启动来宾。
2. infra-ops 上传固定镜像与证据，生成新的 PVE publish 请求、preview 和当前准入，再经 HTTPS 发布。PVE 发布、VM 克隆、cleanup/retire 使用站点对应的同一互斥范围。

旧模板不必仅为接入而重建。通过新版 read/verify 获得当前 UUID、磁盘和配置事实，按站点验收要求登记新模板记录与当前准入；历史加工和来宾检查未做的就保持未知。VM 消费方直接切换到新记录格式，不自动翻译旧输入。

软件切换后先执行代表性离线入口与隔离检查，再在新授权窗口内串行验证一个模板和一个临时 VM，并按实际归属清理。仅有明确静止 staging 残留的成功发布，可在持久化结果和独立清理待办后结清发布 pending；未知活动、归属或结果收集仍需核清。

## 切换失败时

停用新任务准入，保留原计划、执行目录和原生任务标识，先只读核对。新版失败不会自动恢复旧 helper 或 force 路径。软件版本回退也须确认没有活动任务，保留已产生的新记录；后续写入重新生成相符计划并取得当前准入，不能重放已消费的计划。镜像制品、模板版本撤销与既有 VM 的更新是独立操作，不随软件回退自动执行。
