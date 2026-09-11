# Runtime adaptation validation

日期：2026-09-11。对应 change：`adapt-runtime-config-and-local-execution`。

## 实际结果

- `uv run pytest tests/python tests/ansible -q`：787 项通过；保留已有 passlib/crypt 弃用提示。
- `go test ./...`（`automation/launcher`）：7 个分组测试通过，覆盖兼容性、文件传递、真实进程退出、取消协议、回收失败保留、链接处理及本地镜像别名。
- runtime_config/runtime_execution 的 Pyright 检查：0 errors；shell 语法及修改的 switch validation Ansible lint 检查通过。
- Linux amd64 静态 ELF、Darwin arm64 Mach-O 构建成功，标准 `SHA256SUMS` 校验通过。Go 构建依赖不进入运行镜像。
- 更新后的 shipped-image smoke 和镜像分层内容检查通过；所选镜像断网执行了六类组件的代表性生成。原有 Make 入口继续通过回归。
- 原生 OpenTofu + bpg/proxmox 0.111.1：显式依赖下载、锁文件保持不变、归档恢复及禁止隐式下载的初始化通过。

## 平台与设施边界

| 实际环境 | 已执行的代表性检查 | 结论范围 |
| --- | --- | --- |
| Darwin arm64 客户端，独立 Colima Docker 29.5.2 | 本地只读文件挂载、离线生成、结果回收、UID/GID、0700/0600、来源摘要 | Apple Silicon 上显式运行 linux/amd64 镜像 |
| 同一任务的 Linux aarch64 VM，Linux amd64 启动器经模拟执行 | `--engine local`，客户端与 daemon 共享 Linux 路径；生成及 501 用户结果权限 | Linux Docker 本地入口；不宣称 native amd64 硬件验证 |
| 独立客户端容器与嵌套 Docker 29.8.0 daemon | 客户端配置路径在 daemon 上不存在；显式文件上传、结果回收及 501:20 权限 | 真实 DinD 传输，未依赖共享客户端路径 |
| 临时 Forgejo 15.0.8 + runner 12.13.2，单任务执行 | 原生计划及配套产物生成；真实 S3 写回故障；注入 Docker 回收失败；确认原卷保留后人工收集 0600 恢复 state，并清理该任务资源 | 私有合成仓库 `runtime-test/runtime-test` 的 Actions run 1、最终启动器复验 run 2 均为 success；不代表用户共享 Forgejo 环境准入 |
| 任务专用 MinIO，已启用 bucket versioning | 原生 state 读写、竞争锁拒绝、旧计划拒绝、S3 outage 后真实 errored.tfstate 保留 | 仅 terraform_data 合成资源；MinIO 是测试服务，并非替调用方选择生产 S3 产品 |

运行镜像及 provider 均为 linux/amd64，在 Apple Silicon 上显式模拟。原生 Linux arm64 不开放；工具打包及 provider 评估见[启动器指南](runtime-launcher.md#verification-boundaries)。没有执行真实 PVE、K3s、OPNsense 或交换机变更，也没有发布镜像、Release 或启动器。

远程和本地恢复文件同时写入失败、捕获不可准备、中途捕获失败、取消等异常由定向软件测试覆盖；不把这些测试替身描述为真实存储耗尽。Forgejo 作业中的 S3 写回失败则由任务专用代理拒绝 state PUT 实际触发，原始内容未出现在公开作业日志。回收失败的任务卷在确认受保护副本可读后才由测试步骤删除。

## 35 条需求的分组覆盖

| 需求 | 对应实现与证据 |
| --- | --- |
| ENV-01–ENV-08 | runtime_config；两种布局、facts/场景选择、六组件领域适配、路径与输出保护分组测试 |
| RUN-01–RUN-08 | 原生 Go 启动器、共享容器协议、版本/平台拒绝、local/DinD 实际运行、退出与清理测试 |
| OPS-01–OPS-03 | 禁网且无凭据的生成、单独镜像/依赖准备、锁定 provider 原生归档复用 |
| OPS-04–OPS-06 | 静态操作/副作用表、PVE 无 S3 诊断、明确的主机/集群/root 范围及部分部署拒绝 |
| OPS-07–OPS-08 | 保存计划 A/B 误混用在 SSH 前拒绝、独立目录传递、旧 Make 顺序回归、原生 stale-plan/lock；完整流程仍依赖调用方串行安排 |
| DATA-01–DATA-04 | 按操作选择环境变量与显式文件、owner/mode 检查、输出分类和仅非敏感生成导出 |
| DATA-05–DATA-07 | 调用方 S3 配置、无自动迁移/回退、简明来源/版本摘要、保护捕获及本地/实际 Forgejo 恢复保留 |
| DIST-01–DIST-04 | 双平台启动器产物、架构边界表、安装/迁移/恢复手册、上述实际环境与分组回归 |

GitNexus 对已有 cloud-init artifact 调用的 impact 为 LOW；新入口尚未进入缓存图的符号为 UNKNOWN，已核对实际文本调用及针对性回归，没有把空图结果当作无影响。提交前运行 graph change analysis；图检查不替代以上测试。

## 测试资源

所有本轮 Docker 容器、网络、卷、测试 bucket、私有 Forgejo 仓库和缓存均位于独立 `iaas-runtime-adaptation` Colima profile。该 profile 及其 container data、Docker context、任务临时目录均已删除；原有 default profile 保持 Stopped，配置未改动。已验证的独立构建产物及 checksum 保留在忽略的 `dist/launcher/`，未提交二进制或测试秘密。

## 后续 ARM64 构建扩展（2026-09-11）

- 本地 Apple Silicon / 独立 `iaas-arm64` Colima 的原生 Linux ARM64 镜像构建通过。镜像报告 `linux/arm64`；uv 0.12.9、OpenTofu 1.12.6、Packer 1.16.0 均能执行，架构下载包分别按官方固定 checksum 校验。
- 原生 ARM64 shipped-image smoke 通过：离线生成及过期产物检查、K3s 渲染、OPNsense 插件与参数拒绝、UID、只读/缺失路径，以及 bpg/proxmox 0.111.1 的锁文件只读初始化和 OpenTofu validate。没有连接真实 PVE。
- 镜像层检查通过：文档、测试、凭据工具等排除项不存在，必要许可证保留。
- Darwin ARM64 启动器实际选择 ARM64 镜像，完成 `opnsense/generate` 本地挂载执行和结果回收。
- 75 项 runtime Python 回归、Go 测试以及 CI 基线测试通过；覆盖实际架构能力报告、平台不匹配拒绝和保存计划的跨架构拒绝。旧计划缺少架构字段时需重新生成。
- CI 已配置 AMD64/ARM64 原生 runner 串行构建与同组检查；本地验证不代表 GitHub CI 已运行。此构建阶段尚未调整 Release；后续多架构发布扩展见下文。未新增 Linux ARM64 启动器产物。
- 此次没有重做 ARM64 的 DinD、Forgejo、S3 故障恢复或真实设施验证；前文 AMD64 模拟环境证据不扩展为这些 ARM64 验收结论。
- 共享 Dockerfile 的 AMD64 回归构建、镜像层检查及同组 shipped-image smoke（含 provider init/validate）通过；此轮 AMD64 在同一 Apple Silicon VM 上模拟执行。
- 修改的 Python 文件 Pyright 检查为 0 errors，OpenSpec strict、shell 语法及 diff 检查通过。GitNexus 图变更分析为 MEDIUM；保存计划选择函数的 upstream impact 为 HIGH，影响生成/应用/运行入口，已由对应回归覆盖。
- 测试镜像 `iaas-runtime:arm64-test`、`iaas-runtime:amd64-test` 和构建缓存保留在独立 `iaas-arm64` Colima profile；测试容器均已退出，profile 已停止。原有 default profile 未改动。

## 后续多架构发布扩展（2026-09-11）

- Release 改为两个原生架构串行构建与测试、独立 artifact 传递，再由单个 publish job 发布架构标签和共享版本 manifest。发布前核对来源标签、平台与已测试产物身份；已有标签不覆盖。
- 使用前述两个已验证镜像，在本地临时 Registry 执行真实推送、共享 manifest 创建、同一产物重复发布；两架构均完成匿名 digest 拉取和 capabilities 执行，返回各自正确平台。AMD64 运行仍为 Apple Silicon 上的模拟，ARM64 为原生。
- 两个镜像的 Docker save/load 身份保持检查通过。本地真实执行验证 containerd 的 manifest 身份；经典 Docker config ID 分支由替身单测覆盖。发布脚本区分两种存储格式的身份，不将两者混作同一种摘要。
- 33 项发布/架构/CI 定向测试通过，覆盖首次发布、续发、重复发布、旧单架构标签、内容冲突、平台错误、架构后缀的标签长度边界和 Registry 不可达；发布脚本 Pyright 为 0 errors，16 个 workflow shell 块语法检查与 OpenSpec strict 校验通过。
- 未创建正式 GitHub Release、未推送 GHCR，也未宣称远程发布 workflow 已运行。临时 Registry 使用本机回环 HTTP，仅用于本地测试，正式 GHCR 流程仍使用 TLS 和临时认证目录。

## CI 兼容性复核修正（2026-09-11）

- 镜像验证、构建、发布及匿名消费 job 统一使用固定 SHA 的 `docker/setup-docker-action` 安装 Docker CLI/Engine 29.5.2，并启用 containerd image store，保留发布检查的 `--platform`。通过 `DOCKER_HOST` 保持 daemon 选择，避免临时认证目录使命令回到 runner 预装 Engine。
- 启动器附件上传改用非交互式 Bash，继续由 CI 平台显式注入 `GH_TOKEN`。CI 禁止使用开发者本地 1Password 会话及 shell 启动文件获取凭据；调用方提供所需参数、已解析凭据及受保护文件。需求、设计、合同与使用指南同步该边界。
- 35 项发布/架构/CI 定向测试通过，新增回归覆盖 Docker 基线一致性、认证目录切换后的 daemon 选择配置及 CI 凭据注入；28 个 workflow shell 块语法检查和 OpenSpec strict 校验通过。已核对固定 action 的输入及实现，并确认官方 Docker 29.5.2 的 AMD64/ARM64 下载包可用。
- 此次为 CI 配置及合同修正，未重新构建镜像、触发远程 CI 或正式发布；前述本地 Docker 实测不等同于新 workflow 已在 GitHub runner 运行。
