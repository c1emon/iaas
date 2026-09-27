# Design

## Context

`credentials.py` 已能将 `files.api_ca` 映射为 `PVE_API_CA`，但 VM 的输入选择、运行时配置和 API 客户端未贯通。预检查使用 urllib，读取与结果核验使用 proxmoxer；provider 则在独立进程内运行。现有计划已携带原生 plan、相对路径伴随文件、摘要和固定 runtime，launcher 对传输内容有明确边界。

GitNexus 分析将共享 `api_client` 标为 CRITICAL（read／plan／apply／verify），将 `admit_plan` 标为 HIGH（apply／verify）。这要求定向回归这些路径，不据此扩大为真实集群资格验收。

## Goals / Non-Goals

目标是让一份调用方 CA 在整个 VM 执行链生效，并保持原计划可跨 Runner 使用。输入是 PEM CA 文件，可包含多个 CA 证书；它是公共信任材料，不是 API 凭据。

不增加叶证书指纹固定、自定义 PKI 校验器、在线 CA 下载、全局 trust store 修改、额外服务或逐对象证据。不扩展操作系统／provider 版本支持矩阵，也不重构无关 HTTP 路径。

## Decisions

### 1. 一个入口，按实际操作选择

沿用 `files.api_ca`，通过现有发现和路径映射进入任务，API adapter 沿用 `PVE_API_CA` 内部约定。preflight、health、read 和 plan 可以选择调用方文件；消费原计划的 apply／verify 从伴随材料恢复，不读取当前环境的 CA 路径。offline check／generate 和独立依赖准备不要求或加载该文件。

复用公共信任文件的现有权限与可读性规则，不将 CA 当作需要 0600 的私钥，也不向日志输出证书内容。insecure 判定须早于 CA 内容校验（包括空文件拒绝）、bundle 构建和冻结；当前通用文件准备层会拒绝空文件，接入时须避免它提前校验未使用的 CA 内容。已选择文件的普通路径、访问和传输约束仍适用，不扩大为其他凭据的校验豁免。

### 2. TLS 选择先判断 insecure

| 目标配置 | 有效信任行为 |
| --- | --- |
| `insecure: true`，有无 CA 均可 | 使用现有跳过校验模式，不加载、解析或冻结未使用的 CA |
| `insecure: false`，未提供 CA | 保持系统默认信任 |
| `insecure: false`，提供 CA | 系统公共 CA 加指定私有 CA，保持链、有效期和 IP／域名校验 |

严格模式下，在合并公共根之前单独校验调用方 CA 能被标准 TLS 库加载，再发出依赖它的 PVE 请求；不能只检查合并 bundle 是否可加载，否则已有公共根可能掩盖无效 CA。证书不受信任或身份不匹配时报告安全、可定位的 TLS 失败，不重试为 insecure。使用标准 TLS 库的证书验证，不自行实现证书策略或增加签发质量门禁。

错误须通过现有 runtime／launcher 出口可见：为 CA 准备失败提供固定、不含输入值的安全原因；TLS 握手失败保留失败阶段及受保护诊断位置。当前入口会屏蔽未列入安全原因的异常，实施时须覆盖这个出口，不能只在内部抛异常。无需新增错误协议或输出原始证书、路径、token。

urllib 在默认 SSL context 上追加 CA；需要文件型信任入口的 proxmoxer／Requests 与 Linux runtime 内的 Go provider 使用任务目录生成的“系统公共 CA + 私有 CA” PEM bundle。给本次 OpenTofu 进程及其 provider 子进程设置受控 `SSL_CERT_FILE`，不把任务绝对路径写进原生 plan。该变量不是 provider 专属设置：同进程内使用默认根的其他 Go HTTPS 客户端也可能看到新增 CA。这里保证公共根保留、验证不关闭和显式 backend 信任配置不被覆盖，不承诺按 HTTPS 目标隔离根证书，也不为此增加 provider 包装进程。bundle 是运行时派生文件，不替换宿主机或镜像的 CA 文件。

候选方案中的“只把私有 CA 设为默认 bundle”会丢失公共根，故不采用。任务信任配置不改变其他组件、调用方显式 AWS CA 或 backend TLS 选择；不透传宿主机任意 TLS 环境变量来覆盖原计划。实现时以仓库锁定的 provider 和实际 Linux runtime 验证进程传递。

### 3. 只保存实际使用的私有 CA

严格模式的 plan 在首次使用 CA 前复制到任务拥有的计划目录，后续 Python 请求和 provider 都使用这份副本。这样保存的字节就是计划实际使用的字节，不在 plan 结束后再读取可能变化的源文件。

在现有伴随材料中增加 `trust/api-ca.pem`，在计划 metadata 中记录相对路径和一个 SHA-256，并加入原有 companion 列表；沿用既有原生 plan、target、runtime 关联。只绑定这份新增执行材料，不推广成所有文件的新 hash 系统。系统公共根来自同一已固定 runtime，合并 bundle 每个任务重建，无需快照整个系统 trust store。

apply／verify 使用已保存 CA，校验相对路径、文件存在和摘要后恢复任务信任；缺失或不一致在 PVE API 调用及 backend 初始化、snippet 上传、VM 变更之前失败。当前 `files.api_ca` 不替换原计划材料，也不要求调用方重复提供原路径。需要改变私有 CA 或 TLS 模式时重新 plan；这是输入变更，不由 IaaS 自动轮换证书。

只对实际声明了私有 CA 的计划增加上述要求。未使用 CA 或使用 insecure 的计划不携带 CA，也不新增 CA 准入条件；现有无 CA 计划继续服从既有版本和 runtime 约束。不为可选 CA 引入普遍 schema 切换、旧计划转换器或额外审批。

### 4. 代表性软件验证

复用本地 HTTPS fixture：受信任 CA 成功；错误 CA、空／无效 PEM、过期／未生效服务端证书及 SAN 不匹配明确失败；insecure 在同时提供空／无效 CA 内容时仍跳过证书校验。以 adapter 分组测试确认 urllib 和 proxmoxer 消费相同选择，并检查合并 bundle 保留公共根、公共根不掩盖无效输入。通过 runtime／launcher 出口检查安全错误原因或受保护诊断位置，无需对每个证书反例重复跑整条链。

用一条锁定 provider 的本地 TLS 集成路径验证信任确实生效（可在 TLS 后返回受控 API 响应），避免仅靠 mock 环境变量宣称 provider 支持。用跨目录计划恢复及现有 launcher 传输测试覆盖 CA 随包交付、原路径消失、当前 CA 不覆盖、材料缺失／变化拒绝，以及独立 verify 的使用。沿用已有测试层次，不构建真实 PVE API 的完整模拟器。

## Risks / Trade-offs

- 不同客户端默认根加载方式不同 → 对任务 bundle 和真实 provider TLS 握手做定向验证；不依赖环境变量名称推断成功。
- launcher 只传固定文件集合 → 明确加入 trust 材料传输和结果保留测试，防止本地成功但 DinD 丢文件。
- CA 或服务端证书在计划后变化 → 原计划仍用原 CA 并以执行时标准 TLS 校验；同一 CA 下正常续签且身份匹配无需新计划。需要改变有效 CA 或 TLS 模式时才重新规划；本 change 不管理续签。
- 软件验证不能证明现场网络、权限与 Runner 配置 → 文档只记录实际覆盖；infra-ops 接入目标 runtime 后另行确认现场连通，不作为本 change 的默认扩展任务。

## Migration Plan

后续取得实施授权并确认实现分支后，扩展现有可选输入与伴随材料，运行定向回归，再交付 runtime 和示例。infra-ops 选择新 runtime 并提供 `files.api_ca` 生成新计划。未使用该入口的调用方保持现有行为。若回退 runtime，继续遵守既有 runtime／plan 绑定，重新生成需要执行的计划，不转换已保存材料。

## References

- [bpg/proxmox v0.111.0 TLS connection](https://github.com/bpg/terraform-provider-proxmox/blob/v0.111.0/proxmox/api/client.go)：`NewConnection` 使用 Go 默认根信任及显式 insecure 配置。
- [Go system certificate pool](https://pkg.go.dev/crypto/x509#SystemCertPool)：`SSL_CERT_FILE` 是默认根加载配置，不是单个 provider 或目标域名的隔离配置。
- [Saved-plan baseline](../../specs/runtime-saved-plan-execution/spec.md)
