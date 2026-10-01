# 实施与验收状态

## 软件验证

环境为 macOS ARM64、项目 uv Python 3.12、OpenTofu 1.12.6。launcher Go 全套测试通过；runtime 代理/恢复/dispatch、saved-plan、cloud-init/库存、依赖与 private-CA 定向回归通过。修改 Python 文件 Pyright 0 errors；OpenSpec strict 通过。完整仓库验证见下方固定发布记录。

验证覆盖六变量合同、Basic 编码与错误脱敏、诊断持久化前跨读取边界保护、动态来宾凭据拒绝、正式 execute 的 local/DinD 传递 fixtures、Docker 默认值清空、旧 capability 拒绝、离线隔离与准备阶段凭据排除。归档成员/锁匹配与还原后原生 readonly init 独立验证：正确包成功、篡改包失败、锁文件不变，未读取 backend/state。原生 checksum 测试使用合成 package，不作为实际 provider 下载证据。

GitNexus impact/detect-changes 已执行。共享捕获、库存校验和凭据入口涉及 CRITICAL 调用链；改动保持执行、state/recovery 与显式直连 transport 语义。图存在动态解析和宽泛名称匹配限制，结论结合直接 source 与定向回归。

## 固定发布与真实消费

发布为 [v0.1.0-rc.19](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.19)，固定提交 `bd3888cd6bb412affbb9453c418376936d708e90`。[正式发布作业](https://github.com/c1emon/iaas/actions/runs/36753619480) 重跑后全部成功，包括 amd64/arm64 发布与匿名消费；仓库检查为 1936 passed、4 skipped，Pyright 0 errors，Ansible lint 通过。重跑仅处理 GitHub 下载端点的临时 HTTP 500，未修改固定源码、provider 锁或 checksum 规则。历史版本未覆盖。

- runtime：`ghcr.io/c1emon/iaas-runtime@sha256:6332634dcafb2a723e7ad6dcd2c62e998ed8a3664eaa94b29eba968356160f13`。ONE 实际 capabilities 为 `network_proxy_version=1`。
- Linux amd64 launcher SHA256：`c9150397f759d46003dd86078530c72e99de6833575fabbabc6f404f0c0653a2`。
- macOS arm64 launcher SHA256：`1912bdd79f35ed2aebe66d018f7bc4b10e4bab0f7c63b0d8b7eafc1ccbb4edde`。两者均与官方 `SHA256SUMS` 匹配。

2026-10-01 ONE 实际消费通过，环境为 Linux amd64、宿主 Docker 29.7.2、嵌套 DinD 29.8.1，DinD 固定为 `docker@sha256:3f3c01aaaebf7cce837356b688b7c059a4749f10bd7660dec7c58fc454a283f0`。正式发布 launcher 与 runtime 完成 local/真实 DinD 各 8 个用例，共 16 个：

- 任务内网无法直连外部 provider；无代理下载在原生阶段失败，普通/Basic 代理实际下载 bpg/proxmox 0.111.1 并产生合锁归档，认证拒绝与失效代理均非零且有阶段诊断。
- 非 loopback 模块目标 NO_PROXY 命中时目标请求 1、代理请求 0；不命中时目标请求 1、代理请求 1，两种 engine 相同。远程 Docker 控制地址显式列入 NO_PROXY，避免 HTTP_PROXY 干扰控制 API。
- 离线 check 使用 `network none`，十个代理变量明确清空，代理请求无增加。准备阶段未选择或传递设施凭据/backend/state 诱饵；调用者锁文件不变。归档、摘要、诊断与普通输出未发现合成代理认证材料。

实际下载的 Basic 归档在固定 runtime 的 `network none` 容器中独立还原并运行 backend-disabled、readonly 原生 init：正确包 exit 0；篡改 provider executable 后 exit 1 且明确 checksum 拒绝；两者锁文件不变。Docker 28 的文件子路径挂载在 ONE 失败，未进入 runtime；验收结论限定到上述实测 daemon，不修改发布版 launcher 来扩展兼容矩阵。

ONE 清理已完成并复核：任务容器、专属网络、嵌套 daemon/匿名存储、本次新增 runtime/DinD 28/29 镜像和 `/tmp/iaas-controlled-proxy-20261001` 均不存在；保留本地安全摘要，未使用全局 prune，未修改共享网络策略或现有基础设施。上述结果属于软件与真实容器/网络消费验收，未执行真实 PVE 设施操作，不代表生产资格。
