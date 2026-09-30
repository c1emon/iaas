## 1. 合同与入口

- [ ] 1.1 实现六变量的统一大小写/空值/冲突合同，校验无认证及 Basic userinfo HTTP/HTTPS endpoint（含合法 percent-encoding），错误不回显认证或配置值；定义 NO_PROXY 和非支持通道边界。
- [ ] 1.2 将支持/清空的代理名称列为保留名称，在动态 cloud-init 凭据发现/读取/渲染前拒绝大小写名称冲突；代理不进入设施 credential_names。
- [ ] 1.3 runtime capabilities 声明 network_proxy_version=1（包含认证保护及支持路径范围），仅有效联网操作有非空代理项时检查该能力，更新文档和代表性 fixtures。

## 2. 受控传递

- [ ] 2.1 launcher 在 local/DinD 中按有效 network effects 注入规范化代理，清除 Docker 自动代理默认值和 image ENV 的隐式影响；不传任意宿主机环境。
- [ ] 2.2 runtime 按有效操作独立校验，将代理传到实际联网子进程及已有环境代理客户端（如 image base urllib）；明确 PVE 显式直连 API/上传/模板下载的覆盖排除并保留 transport，保留现有白名单与离线 network none。
- [ ] 2.3 保留 prepare-dependencies 的无设施凭据/无 backend/state 输入边界、readonly lockfile、checksum 和归档校验，不调整 provider 打包方式。
- [ ] 2.4 通过受控环境注入 Basic 认证；配置/客户端错误在输出或代理错误诊断持久化前保护认证 URL、username/password、编码与 Basic header，保留其他敏感 recovery 及原生 state 文件处理；报告配置拒绝/阶段非零失败，不直连降级或关闭 TLS，不将代理配置持久化到计划/归档/摘要。

## 3. 定向软件验证

- [ ] 3.1 覆盖大小写单侧/同值/冲突、空值、非法 URL、Basic 认证/编码/认证拒绝、动态凭据保留名称冲突、旧 capability 和非支持变量；代表性反射错误及持久化代理诊断不泄露 username/password/userinfo/header。
- [ ] 3.2 覆盖正式 launcher 的 local/DinD 传递与 Docker 默认值清除、runtime → 实际联网子进程、已有进程内环境代理与保留直连路径的边界、离线无代理且隔离。
- [ ] 3.3 回归无代理直连、准备阶段无设施/state 凭据/文件、锁文件不变、还原成员/锁匹配检查；增加还原后 backend-disabled readonly 原生 init 的正确包/篡改包 checksum 正反例，检查普通输出与计划/摘要/归档未持久化代理认证。
- [ ] 3.4 运行范围匹配的 Python/Go、合同文档/OpenSpec strict 校验；编辑/提交前按项目规则进行 GitNexus impact/detect-changes。

## 4. 固定版本与消费验收

- [ ] 4.1 按现有 release 流程发布 runtime/launcher，记录固定版本/digest/checksums 与代理 capability，不覆盖历史版本。
- [ ] 4.2 在已授权 ONE/等价隔离环境，通过固定版本正式 launcher 的 local 和真实 DinD 完成无直连/有代理的 PVE prepare-dependencies 正反例及 Basic 认证成功/失败，确认实际下载、合锁归档和公开材料无认证泄露。
- [ ] 4.3 验证非 loopback 目标 NO_PROXY 命中/不命中、失效代理非零可诊断、离线仍隔离及设施凭据/state 诱饵无访问，不修改共享网络策略。
- [ ] 4.4 更新简明验收记录，区分 fixtures、实际容器/网络消费与设施验收，按实际结果勾选任务；合并/PR 前同步真实状态。
