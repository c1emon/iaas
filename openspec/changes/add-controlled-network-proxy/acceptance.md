# 实施与验收状态

## 软件验证

环境为 macOS ARM64、项目 uv Python 3.12、OpenTofu 1.12.6。launcher Go 全套测试通过；runtime 代理/恢复/dispatch/依赖校验 75 passed，saved-plan/凭据输入/边界操作回归 78 passed，cloud-init/库存与依赖校验 103 passed。新增现有 urllib Basic 下载与 checksum 反例后，代理/保留名称/依赖定向复验 44 passed。private-CA 诊断合同更新后整组 24 passed；增加非 UTF-8 percent-decoded Basic 字节保护后 proxy/recovery 40 passed。修改 Python 文件 Pyright 0 errors；OpenSpec strict 通过。

验证覆盖六变量合同、Basic 编码与错误脱敏、诊断持久化前跨读取边界保护、动态来宾凭据拒绝、正式 execute 的 local/DinD 传递 fixtures、Docker 默认值清空、旧 capability 拒绝、离线隔离与准备阶段凭据排除。归档成员/锁匹配与还原后原生 readonly init 独立验证：正确包成功、篡改包失败、锁文件不变，未读取 backend/state。原生 checksum 测试使用合成 package，不作为实际 provider 下载证据。

GitNexus impact/detect-changes 已执行。共享捕获、库存校验和凭据入口涉及 CRITICAL 调用链；改动保持执行、state/recovery 与显式直连 transport 语义。图存在动态解析和宽泛名称匹配限制，结论结合直接 source 与定向回归。

## 固定发布与真实消费

`v0.1.0-rc.17` 固定到 `e66a863b0a9da4218722c5213c24baec4a82cdd9`，发布作业 `36750953794` 的 amd64 仓库检查为 1931 passed、3 failed、4 skipped：三项旧 private-CA 测试断言未包含新增阶段诊断字段；runtime 镜像未完成发布。修正断言并增加代理认证反射的 TLS 诊断验证后发布新版本，不覆盖 rc.17。rc.18 已启动正式发布；随后的认证保护复核发现合法 percent-encoding 原始字节与 Unicode 替换解码的 Basic header 表示差异，已补充原始字节脱敏及回归。最终消费将固定包含该修正的新版本，待记录成功版本 digest/checksums。ONE SSH/Docker 可达（Linux amd64，Docker 29.7.2）；正式 local/真实 DinD 的隔离网络下载、Basic 正反例、NO_PROXY、离线与诱饵边界尚未执行，任务 4 保持未勾选。测试结束将清理本次容器、网络、卷及临时文件，不改变现有基础设施。
