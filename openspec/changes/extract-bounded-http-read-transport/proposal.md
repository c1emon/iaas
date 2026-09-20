# 提取有界 HTTP 读取传输

状态：设计，未实施。序列第 3 项，前置 `add-fast-offline-validation-profiles`。

## Why

OPNsense workflow reader 与 readonly diagnostics 重复实现请求超时、响应流大小上限、HTTP 失败分类和关闭响应。复用这部分机制可以避免修复只覆盖一个入口，同时保留不同领域的状态与端点准入。

## What Changes

- 增加无设备领域依赖的 HTTP 读取传输包，统一有限 timeout、响应大小/累计预算、资源释放及安全错误代码。
- 首批接入两处现有 OPNsense 读取适配器；端点、凭据、分页和观察状态继续由各自适配器负责。
- 不自动重试，不迁移写入器或替换 proxmoxer，不对调用方开放任意 HTTP 入口。

## Capabilities

### New Capabilities

- `bounded-http-read-transport`: 对内部已准入只读操作提供有界响应读取及稳定失败机制。

### Modified Capabilities

无。OPNsense 领域已有状态、准入和覆盖合同继续有效。

## Impact

涉及新 `iaas_automation/http_transport/`、workflow reader、diagnostics adapter 及相关测试。使用已有 requests 依赖；不把在线 adapter 放进禁止在线行为的 common primitives，不移动领域 endpoint 白名单。
