## Context

实施状态更新：已进入 `feat/separate-image-build-and-pve-publish`，保留工作树修改，并正常归档前置 `adapt-pve-ci-lifecycle`。以下背景记录设计时的原实现；当前进度见 [实施记录](../../../docs/operations/image-publish-implementation.md)。

2026-09-23 当前分支 `feat/adapt-pve-ci-lifecycle` 的实际代码已不同于旧 foundation 描述：`automation/packer/proxmox/debian-13/packer.pkr.hcl` 只有变量，没有 builder/build；同目录 `build-template.sh` 已 fail closed。真正的加工在 `iaas-pve-template-worker`：下载并 SHA-512 校验、复制镜像、virt-customize 设置 Debian 软件源/包/时区/locale、virt-sysprep 清理，再 qm create/importdisk/set/template。当前配置验证不等同于来宾启动验收。

GitNexus 指向 contracts.validate_request → runtime.run/_poll_remote → runtime_execution.main；索引落后 12 commits，extensionless worker 无完整调用图，已用当前源码确认边界，不能以图的 LOW 风险证明整体迁移安全。本 change 只新增设计文件，不修改函数。

本轮比例复核的合同文件impact返回UNKNOWN（新文档未入图）；已直接核对合同、全部delta及infra-ops消费方，不能以未命中图当作无影响。用户已授权收窄六项过度门禁，以下为修订后的设计，早期review决议以最新比例复核记录为准。

现有 `adapt-pve-ci-lifecycle` 已在代码实现但尚未归档，其 pending/准入、原生对象关联、未知结果和归属感知清理必须保留。本 change 仅替代模板构建执行位置与相关协议，不重写 VM state 或 OPNsense 的原生流程。

## Goals / Non-Goals

提供两个可以单独调用的通用工具能力：镜像构建、PVE 模板发布。infra-ops 不复制已有加工实现，iaas 不调度远端执行器、不解析 1Password、不管理 CI/制品保留/可用版本名单。不要求发布镜像必须由 Packer 生成；外部镜像也须满足相同磁盘与兼容性合同。

首期支持 Debian 13 amd64、单盘自包含 qcow2、声明 BIOS 或 UEFI、Cloud-init 与 guest agent；不自动声称跨架构、Secure Boot/vTPM、多盘或任意发行版可用。不以可配置包版本或 pinned base 声称 bit-for-bit 可重现。

## Decisions

### 1. 明确职责和权威合同

| 内容 | iaas | infra-ops |
| --- | --- | --- |
| 配方 | 通用 Packer QEMU backend、版本化 Debian profile、可复用定制与清理步骤 | 选择 profile/base/version、镜像软件组合、软件源和站点参数 |
| 执行 | 本地进程、任务目录、超时、结果收集、定向清理 | 执行器、CI/SSH 触发、并发调度与跨任务互斥 |
| 凭据 | 只消费当前操作必要的已解析秘密 | 获取凭据、scope、轮换、trust 配置 |
| 产物 | qcow2、标准 checksum、描述、检查结果 | 上传 S3、固定对象身份、保留和推广 |
| 发布 | HTTPS PVE 适配、任务观察、模板事实、cleanup/retire | 目标、批准、pending/一次消费、当前管理归属和依赖交接 |
| VM | 既有完整 root 的 OpenTofu 生命周期 | 站点 root、backend、业务验收和版本选择 |

[image-publish-v1.md](contracts/image-publish-v1.md) 是双方字段、版本和阶段语义的唯一权威；infra-ops 引用固定 iaas 发布版本及同版合同，不复制定义。实现后将其发布到稳定 docs/schema 位置，change 内保留历史。双方 change 同期设计；iaas 的新 runtime 可用后才启用站点工作流。`publish` 在此表示 PVE 技术发布，不代表 caller 已推广为业务可用版本。用户明确不要求向后兼容：入口选择基于职责，不为旧协议提供别名、转换适配器或双实现。

### 2. image 工具选择 Packer QEMU，复用现有加工内容

标准流程为：固定输入 → 下载验证基础镜像 → Packer 启动临时 QEMU 来宾 → 通过临时 SSH 执行受控 Ansible 配置与服务检查 → 正常关机 → 对最终磁盘执行离线身份清理 → 静态检查 → checksum/descriptor → 本地产物交付。

迁移保留现有软件源、cloud-init/qemu-guest-agent/openssh-server、timezone、locale 和清理语义。Ansible 管理启动状态下的系统配置；libguestfs 保留适合离线执行的清理/校验，不机械改写为在线 rm。不得在 Packer 仍需 SSH 时删除其连接身份；最后一次关机后清理 machine-id、SSH host keys、cloud-init state/log、构建用户/临时 authorized_keys、临时网络设置及 seed、日志、缓存。软件安装成功不证明镜像可启动。

最终 cleaned 镜像不再直接启动。build可按选定策略进行清理后测试，也可由独立 `image test` 对已有或外部镜像执行，不要求重建。测试使用临时副本/overlay，绑定源盘SHA-256、检查策略、runtime及资源预算，输出image-test-result/v1；检查身份重建、Cloud-init和guest agent后销毁副本，不修改原盘或补造历史。UEFI使用fresh VARS，不依赖构建时efivars.fd/Boot条目；此文件不属于单盘交付物。read/verify保持只读。最终输出必须flattened/self-contained，无backing/external data file；首期profile为版本化可信实现，配置数据不接受任意root shell或未支持HCL。

### 3. 执行器是调用前提，不是 iaas 管理对象

image提供check/read/verify和直接build/test/clean，不为可重建本地资源建立强制plan/apply、单次消费或恢复preview。启动时校验并记录实际输入/profile/runtime，任务ID防并发覆盖；刻意重跑使用新任务ID即可。build/test要求Linux amd64、可用/dev/kvm、CPU/内存/磁盘预算及必要网络；固定accelerator=kvm，拒绝偷偷退回TCG。check不启动来宾、不声称KVM已验证；实际构建/测试在启动来宾时确认，不另起一套资格探针或修改宿主机模块。使用用户态NAT/loopback SSH转发，不需PVE bridge/API。

单独发布image-builder OCI runtime（固定Packer/QEMU/plugin/Ansible/libguestfs），普通PVE/OPNsense runtime不引入KVM权限。launcher仅对image build/test开放精确设备和挂载，禁止通用privileged、宿主Docker socket、宿主根目录或任意设备透传。image check可离线无凭据；可选dry-run仅展示检查/清理候选，不产生审批令牌。DinD需满足实际KVM/挂载/输出条件，否则明确unsupported；不要求所有历史运行模式具备KVM。共享的是dispatcher、输入隔离和结果规则，不强求每个工具都有相同操作。

任务仅在当前执行器执行，无新 daemon/远程队列。进程组/cgroup 和私有持久任务目录绑定 execution_id；受控取消终止并等待任务拥有的 Packer/QEMU/libguestfs 子进程，回收工作文件。强杀/重启或结果收集不完整时保留未知状态与材料，下次 read 检查实际进程/容器/任务句柄；记录 running 或 PID 本身不证明活动。临时 overlay、seed、密钥、端口和磁盘归属于本次任务，cleanup 不触及共享 cache/其他任务。

### 4. 制品存储由调用方完成，不重新包装 S3 平台

iaas交付磁盘和descriptor，infra-ops用标准S3工具上传。默认核对标准传输成功、对象大小和固定key/version，再发布descriptor作为上传完成点；标明uploaded与content_verified的区别，不默认再全量GET/hash，独立回读是可选站点强化。publisher消费时必须在PVE写入前流式校验实际磁盘SHA-256，ETag不替代它。descriptor经严格schema校验（拒绝重复键）后按规范化语义绑定，空白/键顺序变化不重plan，任何语义变化仍需新发布plan。相对disk.path不变成S3地址；额外test_results独立交接并绑定同一disk/check scope，不静默改写已选检查策略。外部镜像历史保持unknown，可直接test取得新证据，不补造早期清理记录。

### 5. PVE 发布使用外部 HTTPS 客户端，私有源不直接交给 PVE

默认传输路径为 `controller-upload`：iaas 发布 runtime 从调用方提供的受保护 HTTPS locator 下载 → 流式 SHA-256 与大小核对/格式检查 → 官方 multipart upload(content=import) → import-from → 配置 → template。S3 locator 可以是短期签名 URL，但只在发布 runtime 内消费，不写 preview/descriptor/普通日志，也不传 PVE。locator 与稳定 object_ref 分离，凭据更新不改变固定镜像身份。

原因：PVE 官方 `Tools.pm::download_file_from_url` 会将完整 URL 输出任务日志且传 wget argv。直接给 download-url 传预签名 URL 与当前秘密最小化合同冲突。因此本次不实现 node-download 捷径；PVE 只收到受控文件名及文件字节。HTTPS 下载采用显式 trust、超时/大小限制，禁止凭据重定向、默认代理或跨 origin 跳转；内部镜像服务必须由 caller 显式允许。发布 API 使用 caller token+CA 校验主机名，不复用节点 root ticket 探针。

默认预检本地下载盘与API可见import/images存储，按virtual size估算最终盘、按已知共享关系累计占用。已知不足、API/存储明确不支持或已知上传限制仍阻断。PVE接收端/var/tmp、代理限制及不可观察的文件系统共享关系作为站点部署约束、保守预算与诊断信息，缺精确遥测本身不阻断，也不声称空间充足；本change不新增SSH/space helper。可另行选择站点监测强化，但不成为通用发布前提。不能把storage avail等同/var/tmp；任何预检都不预约空间，实际ENOSPC、上传拒绝和超时按正常失败/未知结果恢复处理。目标与TLS身份依然必须明确。

PVE `import` 暂存与最终 `images` 存储分别选定；不是所有 storage 都支持 import、cloud-init、EFI 或所需格式。目标节点可见性、enabled/active/content、权限、空闲 VMID（有完整读取权限的 VM 清单）、bridge、BIOS/UEFI 兼容须在 plan 和 apply 锁内核对。source volume 使用合法 PVE volume ID（含目录斜线），不传任意宿主绝对路径。

### 6. 发布任务编排保留不确定性与当前准入

调用方在 apply 前持久化单次消费/pending 并持有覆盖同目标发布、clone、cleanup/retire 的互斥；iaas 校验绑定，保持 task-owned journal 到交付。首个网络写入前记录 phase intent，返回 UPID 后立即持久化，逐步轮询确认完成再执行下一步。上传、create/config-import、template、delete 的异步返回按固定版本接口适配，不能假定每个 API 都同步或都有 UPID。

controller 退出时 PVE 原生任务可能继续；后续 read 只查询原 UPID/明确对象/文件及 intent，不自动恢复剩余变更。请求可能被服务端接收但响应丢失时 effects=unknown，即使存在同名文件或空闲 VMID也不自动重试 POST；先核清，之后新的 plan/execution。观察到符合配置不证明原 apply 成功。若原生任务无法唯一关联，明确保留人工核清入口，不虚构 exactly-once API。

新发布使用空闲 VMID和独立版本；创建前固定原生 SMBIOS UUID及任务标识，用来核对对象，不把标签当不可伪造凭证。成功结果须同时包含对应UPID stopped/OK、实际 template flag、UUID、volume refs、关键硬件/Cloud-init 配置和逐阶段结果；上游先写template flag再转换磁盘，不能只看标志。业务可用状态由 caller 决定。VM消费方直接更新为新template-record合同及其当前template_admission，不提供旧record转换适配器；缺字段/版本不支持阻断，不能退回仅按VMID。

官方upload可能覆盖同名文件，必须使用执行唯一文件名、互斥及预存在拒绝，不能复用未知归属文件。上传的Datastore.AllocateTemplate权限不包含删除import文件所需的Datastore.Allocate；调用方应为专用staging存储授予完整且受限的闭环权限。导入使用PVE volume ID和对应读权限，不要求root@pam绝对路径导入。任务查询须覆盖原执行身份及恢复身份。

### 7. 清理按资源所在阶段与当前归属划分

image clean直接选择原任务，在同一资源锁内核对进程已停和路径/资源归属，向原记录追加清理attempt；无需新preview/execution/recovery_of，不删除shared cache或已交付产物。publish cleanup仍plan/apply，只处理原发布执行可证实拥有、原生任务已停止且仍由publisher管理的暂存文件/未完成VM/卷。未知任务活动、关联不清或已移交OpenTofu的对象均拒绝删除。API上传中断只留下PVE内部临时文件时记录未知，不通过任意root rm扩大能力。

完整模板必须action=retire并有当前caller授权/依赖结论；未知或linked clone依赖阻断，独立full clone不被误认依赖。PVE cleanup/retire仍有新plan/execution，cleanup及恢复要求recovery_of，普通retire不伪造历史。若全部原生任务已停、模板创建/转换/配置验证成功且结果已完整收集，只剩确切已知归属的静止staging文件，返回status/publication=succeeded、cleanup=failed及warning/残留清单，模板可以消费。caller先持久化终态和独立清理待办再结束本次pending，不为静止残留保持全局互斥；后续只清staging的新PVE cleanup不得选择已完成模板。任务活动/归属/模板验证或结果收集未知仍阻断并保留pending。这个例外不改变VM/state/OPNsense恢复，retire不删S3镜像。

### 8. 协议切换、helper 退役和旧材料

| 当前实现 | 后续处理 |
| --- | --- |
| worker 的 download/customize/sysprep | 抽取到 image 工具；下载基础 SHA-512 校验保留，最终制品统一 SHA-256 |
| worker 的 qm create/importdisk/set/template | 移到外部 PVE HTTPS adapter；不保留 CLI 写入 fallback |
| helper 的执行/对象记录、准入与 cleanup | 保留语义，迁为外部 journal+UPID+API观察 |
| node storage-status root ticket probe | 发布路径改用外部 TLS API；无剩余调用时删除其安装资产/权限 |
| cache/work 空间检查 | image与publisher分别检查本地；PVE端采用API可见存储信息，不新增空间探针 |
| snippet-upload | 独立 VM/snippet 能力，当前不因模板重构删除或扩大权限 |
| placeholder Packer/旧env生成与文档 | 替换为真实QEMU profile与新build/publish输入，旧入口明确迁移错误 |

归档/应用顺序：先完成 `adapt-pve-ci-lifecycle` 的正常归档（本次不执行），再应用本 change；其模板五项 requirements 在 delta 中显式移除并替代，VM原生plan/state及其他合同不受替代，仅模板引用直接改为新record。发布前停用旧构建入口，核对无活动 worker，导出旧 private records并完成pending归属交接，才卸载 systemd worker/helper/sudo条目和依赖。不能因“精简”删除唯一旧记录或强杀活动任务。旧preview/record只保留原始文件供人工调查，新工具无需解析旧schema；已有模板通过新read生成全新的current observation，构建历史保持unknown，重新plan并取得当前准入。不提供回滚到旧force写入路径；软件回退同样要确认无新任务、保留证据并重新plan。

## Risks / Trade-offs

- Packer在线配置新增启动/网络前提，但支持实际启动检查；最终清理不再启动原盘，减少身份污染。
- controller-upload增加本地落地与传输以避免私有URL进PVE日志；默认不增加上传后全量回读，容量预检保留可观察边界并处理真实运行失败。
- KVM执行器由infra-ops安排，不将macOS、普通DinD或现有节点默认视作满足条件。
- 上游master说明API方向，不证明目标版本/第三方存储已可用；固定API版本/权限及代表性目录和目标存储验证为实现任务。若官方上传仍暴露凭据或缺少必要能力，应修改设计后实施，不临时扩大root桥接。
- 采用当前必要的字段和代表性正反例，不为未来租户/多云/签名链建框架。真实环境与发布操作需另行安排窗口，旧四小时授权不延续。

## Validation and delivery

本次交付通过双仓strict validate、合同链接/字段对照和多agent边界/API/失败路径复核。后续验收区分：静态schema、替身API失败测试、本地KVM构建、真实PVE发布、克隆首次启动、业务可用。软件结果不替代现场结论。

代表性覆盖包括：自包含磁盘与错误摘要/外部backing，清理后副本首次启动，KVM缺失，拒绝跨阶段凭据，upload响应丢失/ENOSPC，import/template UPID失败，配置漂移/VMID重用，活动或OpenTofu所有对象的cleanup拒绝，完整模板retire和独立full clone。用户已允许较大代码改动，但本change的编写不等于授权新增现场资源。

## References

- [Packer QEMU builder](https://developer.hashicorp.com/packer/integrations/hashicorp/qemu/latest/components/builder/qemu)
- [PVE Storage API](https://github.com/proxmox/pve-storage/blob/master/src/PVE/API2/Storage/Status.pm)
- [PVE download implementation](https://github.com/proxmox/pve-common/blob/master/src/PVE/Tools.pm)
- [PVE Qemu API](https://github.com/proxmox/qemu-server/blob/master/src/PVE/API2/Qemu.pm)
- [Existing lifecycle change](../archive/2026-09-23-adapt-pve-ci-lifecycle/design.md)
