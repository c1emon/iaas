# 设计

## 1. 当前链路与边界

- `automation/launcher/execute.go:execute` 从 discovery 的 `credential_names` 组装 Docker `--env NAME`，没有代理通道。
- `src/iaas/runtime_execution/operations.py:process_environment` 只保留 runtime 和操作凭据白名单；`Execution.run` 将该环境交给 `run_protected`，所以容器变量不等于工具收到变量。
- `prepare_dependencies` 已使用 `tofu init -backend=false -input=false -lockfile=readonly`，比较准备前后的锁文件，生成限定成员的依赖归档；当前文件选择不读取 backend，凭据选择为空。保留这些边界。

GitNexus 将 `process_environment` 和 launcher `execute` 的已解析影响均评为 LOW；前者连接 runtime main，后者连接 launcher main。Go `execute` 图结果是 lower-bound，存在未解析调用，实施前需以直接代码及 local/DinD 回归补足，不能把图计数作为全部覆盖证明。

## 2. 配置入口与规范化

入口为调用 launcher 时显式提供的六个标准环境变量，不在环境 YAML、runtime image 配置、request、plan 或 backend 中增加代理值。直接调用 runtime 时可通过容器环境提供同一入口。

| 逻辑项 | 接受的变量 | 语义 |
| --- | --- | --- |
| HTTP 目标代理 | `HTTP_PROXY`、`http_proxy` | HTTP 目标请求的代理 URL |
| HTTPS 目标代理 | `HTTPS_PROXY`、`https_proxy` | HTTPS 目标请求的代理 URL；可使用 HTTP CONNECT 代理 |
| 绕过列表 | `NO_PROXY`、`no_proxy` | 逗号分隔列表，匹配的目标按工具原生规则直连 |

每对变量去除首尾空白，空串视为未配置；两个非空值必须逐字相同，否则在实际联网工具启动前拒绝，只报告变量名/错误类型。单侧非空即为有效值，输出给工具的两种大小写必须一致。HTTP 与 HTTPS 是独立项，不替调用方把一个补到另一个；仅配置一项不会保证另一种协议使用代理。

代理 URL 必须是显式 `http://` 或 `https://` URL，包含有效 host 和合法可选 port；不接受控制字符、路径（除空路径或 `/`）、query 或 fragment。支持无认证以及 URL userinfo 中的 Basic 用户名/密码，例如文档占位符 `http://<user>:<password>@<proxy>:<port>`；保留合法 percent-encoding，校验错误不得回显完整值。用户名须非空，密码可为空；不额外推断凭据、不调用本地 1Password，也不承诺 NTLM/Kerberos 等协商认证。`ALL_PROXY/all_proxy`、FTP/SOCKS、任意宿主机变量不属于支持通道。

六个代理变量均为保留运行时名称；cloud-init `password_env`、`public_key_env` 等动态凭据声明不得选择它们，按大小写不敏感的保留集合检查，并在 discovery 返回凭据名称、读取对应值或渲染前拒绝冲突。被清空的 ALL_PROXY/FTP_PROXY 通道同样不可作为动态来宾凭据名，防止清空策略与凭据注入争用。代理值不加入设施 `credential_names`，也不被渲染进来宾材料；NO_PROXY 本身是网络配置，不成为来宾凭据。

NO_PROXY 保留调用方的列表内容，不自动加入 PVE/S3/内部地址、不强制 `*`，不把列表解释为设施权限。文档明确支持工具的原生匹配语义；验收至少使用精确非 loopback hostname/IP，不能用 Go 默认绕过 localhost 的行为冒充 NO_PROXY 生效。域名后缀、port、CIDR 等能力以选定工具为准，不承诺所有工具具有相同语法。

## 3. local/DinD 传递与兼容检查

launcher 在确认所选操作的有效 `effects.network` 后，独立于 `credential_names` 构造代理通道。允许联网时规范化、校验并通过 Docker 子进程环境及 `--env NAME` 注入，不将 URL 放到命令行；local bind 和 DinD volume/copy 模式均使用该受控集。

有效操作允许联网且任一受支持代理逻辑项非空时（包括仅 NO_PROXY），launcher 要求 runtime capabilities 的 `network_proxy_version: 1`；缺少/不支持则明确拒绝，不能对旧镜像静默运行并丢掉配置。未配置或离线操作不增加该兼容要求，离线也不解析认证值；不为此升级 facility request/admission 或 launcher 总 interface 版本。

launcher 创建的执行、capabilities、discovery 和传输容器须防止 Docker client `proxies` 默认值或 image ENV 隐式启用代理：对支持的代理变量明确设置规范化值或空值，对不支持的自动代理通道如 ALL_PROXY/FTP_PROXY 明确清空。capabilities/discovery/离线及传输容器不使用代理。该处理只影响任务容器，不修改 Docker context、daemon 配置、host 环境或 image 拉取策略。

runtime 再独立按有效操作 effects 校验及规范化同一入口；只把受支持的代理变量合并进现有子进程白名单，并在已有使用环境代理的进程内客户端初始化前应用相同规范化值。保留全部已有禁止项，不因代理开放 OP_*、AWS_*、TF_VAR_*、动态命令或任意环境透传。离线操作不解析/使用代理值，不向其工具环境放行代理，容器继续 `--network none`。

本次支持边界如下，`network_proxy_version: 1` 表示这些受控环境传递语义，不表示代理接管所有网络：

| 路径 | 本次保证 |
| --- | --- |
| 声明允许联网的实际工具子进程 | 接收规范化六变量；OpenTofu 依赖下载为必须验收路径，Packer 等已有采用环境代理的工具沿其原生行为使用；不增加任意命令通道 |
| 已有采用标准环境代理的进程内客户端，如 image `_download_base` 的 urllib 下载 | 使用同一规范化值并保护错误输出；不绕过其已有 checksum/TLS 规则 |
| PVE `PveHttpsClient`、直接 HTTPS 上传、模板 `_download` 等显式直连实现 | 保留原有直连选择，不在本 change 中替换其设施/制品 transport；文档明确不受该环境代理保证覆盖，不能将这种原有直连报告为代理成功 |

OpenTofu/provider 子进程内已经采用标准环境代理的请求仍按原生规则处理；调用方通过 NO_PROXY 选择需要直连的设施地址。上述显式直连客户端的覆盖不能从 operation 的 network=true 或总 capability 推断；要扩展它们需明确的 transport 变更及相应验证。

代理地址必须从实际 runtime 容器可达；DinD 中 `localhost` 不指向 launcher 宿主机。代理仅作用于采用受支持 HTTP/HTTPS 代理机制的联网工具，不代理 SSH、原始 socket、Docker daemon image pull，也不是新的 egress firewall。

## 4. 失败、输出与权限

没有代理时沿用直连。代理连接/CONNECT/代理 TLS 失败沿用工具非零结果，不能删除变量重试直连、切换其他代理或增加 insecure 选项。NO_PROXY 命中以及未配置的协议按已声明语义直连，不属于故障降级。

普通错误报告区分配置拒绝和工具阶段失败，工具失败给出非零退出码、阶段、代理是否配置及受保护诊断位置；不把所有下载失败都错误归因为代理故障。复用现有受保护工具捕获，不回退到终端原始 stdout/stderr。配置错误、代理/客户端异常及任何公开诊断必须在输出前脱敏，保护完整认证 URL、userinfo、用户名/密码及其 URL 编码、Basic Authorization 表现形式；不能只去掉 password 而回显 username。代理认证失败（如 407）、连接拒绝、超时或 TLS 失败均不得回显认证，也不得直连重试。以代表性工具错误/恶意回显 fixtures 验证该边界，不建通用日志系统。

代理值不得写入 summary、provenance、输入映射、request/admission、saved plan metadata 或依赖归档；不得为输出配置而 dump 环境。代理错误文本中的认证材料在持久化工具诊断/错误捕获前也须脱敏，不能以 recovery 目录权限作为例外；其余受保护工具输出继续沿现有敏感捕获/回收规则处理，不直接发布原始内容。不得为代理脱敏删除或重写设施原生 state/recovery 文件，不把其内容送入普通日志。认证值只通过调用方提供的环境和受信 Docker daemon 注入；Docker 容器配置及受保护进程环境可由其授权管理员查看，不宣称环境注入对 daemon 管理员隐藏密码，任务清理沿现有生命周期执行。

`prepare-dependencies` 仍声明 network=true、state=false、infrastructure_write=false；不读取设施 token、SSH key、S3 凭据、backend/state/admission。只消费原有完整 root/锁文件并生成本地依赖归档。保留锁定版本、readonly lockfile、provider checksum 和归档成员/锁匹配校验；代理不会生成新 trust material、关闭 TLS 或配置不校验 checksum 的镜像源。

## 5. 验收与交付

软件回归覆盖大小写单侧/同值/冲突、空值、非法 URL、无认证/Basic 认证（含合法 percent-encoding）、认证失败及代表性错误脱敏、动态来宾凭据与保留名称冲突、子进程白名单、实际联网子进程收到值、离线隔离、Docker 自动代理默认值清除、旧 capability 拒绝、local/DinD 传递及输出不含值。进程内环境代理客户端与明确保留直连的 PVE 客户端各取代表性路径，防止误改路由或过度声明。无需穷举所有组件和工具版本。

正式消费验收使用固定 launcher/runtime（实施后发布版本）和测试专属输出目录：

1. 在 ONE 或等价已授权 Linux Docker 环境中使用任务专属受限网络，分别经 local 和真正 DinD 调用 PVE `prepare-dependencies`。不修改共享主机路由/防火墙，不读取真实 PVE/S3；测试对象是公共锁定依赖。
2. 固定 root、provider 版本、checksum 和平台；使用全新 workspace、不提供 dependencies 归档/已有 provider cache，选择确需下载的锁定 package。相同网络无代理失败，设置代理成功，有代理连接/目标请求证据；仅变量回显或缓存命中不算完成。
3. 核对 caller lockfile 字节不变及下载时 OpenTofu checksum 成功。还原阶段单独复用 `restore_dependencies` 的成员安全和锁文件匹配校验；它本身不检查 provider 内容 checksum，解压成功不算 provider 完整性证明。随后在无 backend/state/设施凭据的全新 root 上，用 `tofu init -backend=false -input=false -lockfile=readonly -get=false -plugin-dir=<provider目录>` 执行原生 checksum 校验；`<provider目录>` 必须取 `restore_dependencies` 返回的目录，即 `<destination>/.terraform/providers`，不能传解压根目录 `<destination>`。正确包成功，保持锁文件不变但篡改 provider 内容的代表性包失败。成员非法/锁不匹配在还原阶段拒绝。不给 provider preinstall 增加新要求，也不新建归档签名/hash 框架。
4. 使用运行工具确会请求的非 loopback 测试目标，NO_PROXY 命中时有直接请求且代理未收到该目标；去掉匹配项后有代理请求。不要用手写 curl 绕开正式 runtime 路径替代验收。
5. 使用失效代理产生可诊断非零失败，没有直连重试或 TLS 降级；配置代理同时调用离线操作，核对 network none 及无代理注入。注入无效设施凭据/state 文件诱饵，确认未发现、未传入、未访问；保留操作 effects 的只读证据。
6. 在上述正式链路加入要求 Basic 认证的代理正例及错误认证反例，使用测试专属认证值、不记录原始认证请求头。核对认证成功下载、认证失败非零且无降级，并扫描普通日志、错误输出（包括持久化代理错误诊断）、计划/摘要/归档等约定材料，确认无 username/password、userinfo 或认证 header。预配置的目标地址/原始 caller root 不等同于新增代理材料，测试应使用独立的合成认证值以免误判同名文本。

记录环境、命令类别、版本/digest、结果和权限边界，不保存代理认证或原始环境。现场网络尚未可用时保留验收任务未完成，不用 fixture 结果替代。release 继续使用现有流程，交付可固定消费的 runtime/launcher；本轮规划不进行构建发布。

## 参考

- [Docker CLI proxy 配置](https://docs.docker.com/engine/cli/proxy/)：client defaults 会注入新容器，应与 caller 显式通道分开处理。
- [Go HTTP proxy 实现](https://go.dev/src/vendor/golang.org/x/net/http/httpproxy/proxy.go)：大小写变量与 NO_PROXY 的工具原生匹配边界。
- [Go HTTP transport](https://go.dev/src/net/http/transport.go)：代理 URL userinfo 转为 Proxy-Authorization；本次限定 Basic 用户名/密码认证。
