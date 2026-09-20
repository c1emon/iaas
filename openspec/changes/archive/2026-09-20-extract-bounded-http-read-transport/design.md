## Context

reader._request 与 diagnostics.Transport.call 都使用 requests Session、(5,15) 默认连接/读取 timeout、stream、禁止重定向和 2 MiB 单响应限制。workflow 还具有 observation budget；diagnostics 具有累计字节预算。重复逻辑需要合并，但结果状态不可混用：workflow 的 failed/incomplete 与 diagnostics 的 error/unsupported 各有合同。

## Goals / Non-Goals

目标是复用已有两个调用方的 transport 机制，不建立跨平台 SDK 或任意请求代理。不改变业务分页、缓存、默认预算、领域 endpoint 范围、凭据载入、写入/激活逻辑；PVE proxmoxer 和 foundation probes 本轮不迁移。

## Decisions

- 放置于 `iaas_automation/http_transport/`，不放 common；独立于 OPNsense/PVE 包，允许依赖 requests 和公共错误原语。domain → transport → common，转换与纯验证层禁止反向导入 transport。
- 接口接收已配置的 session、由适配器批准的请求信息及有限预算。Session 的创建、凭据和关闭由适配器负责；单次 response 由 helper 在所有出口关闭，包括非 2xx、解析失败、超限和 stream 异常。测试注入 fake session 与 clock，不访问设备。
- 固定禁止 redirect，不修改既有 TLS 选择。HTTP GET 或 POST 本身不构成只读证明；POST 查询仅能来自既有固定白名单。公共 helper 不是外部 CLI/API，不能接收 operator 自由 endpoint。写入器不接入此 helper。
- 复用现有 requests，不引入 HTTPX/Tenacity，也不自建通用客户端框架。调用次数保持一次，认证、限流、timeout、5xx 等均不会触发隐式 retry；未来重试须按操作语义另提案。
- 值对象或小型 protocol 表达单响应字节上限、累计预算、可选单调时钟 deadline；资源范围内共享累计计数，不能每页重新清零。继承已有数值及 budget 作用域，显式拒绝非法预算。
- 请求前/返回后/各响应块检查剩余预算，并按剩余值限制连接/读取 timeout；保留现有 budget 测试。requests 的 socket 读取超时不等于操作绝对墙钟上限，本次不声称可以抢占所有阻塞或恶意慢流；绝对耗时机制强化不混入本次提取。
- 基础 helper 返回 decoded JSON 或具有固定 reason/status_code 的安全 TransportFailure；严格拒绝非标准 JSON 常量。不在异常文本中包含 URL、payload、headers 或 backend body。第三阶段只提供传输专用错误，第四阶段再接入公共结构化诊断。
- 领域映射留在适配器：404/405/501 的 capability 语义、401/403 与其他失败继续保持原有公共 reason/status。stream 阶段的 requests 异常也经过相同映射，不能退化为原始错误或成功空集合。

## Risks / Trade-offs

- HTTP 细节混入领域 → 固定 endpoint、分页与结果判定不下沉；两适配器的状态分别回归。
- 有界读取名义上掩盖慢流限制 → 明确 timeout/deadline 观测边界，不宣称严格可抢占总时限。
- 资源泄漏或预算重置 → 请求异常、HTTP 失败、body/JSON 失败、跨页累计超限均用 fake stream 验证 close 与请求计数。

## Migration Plan

先核对分支/impact，添加 helper 及离线测试，再依次接入 workflow 和 diagnostics，保留兼容调用入口。完成两调用方回归和 import contract 更新后交付；回退时一并恢复 helper 与调用方，不改变任何设备状态。
