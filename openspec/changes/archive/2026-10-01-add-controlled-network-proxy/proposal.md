# 受控传递联网工具代理配置

## Why

rc.16 的 launcher 只注入所选操作需要的凭据变量，runtime 的子进程环境白名单也不包含代理变量。容器中已有的 HTTP/HTTPS 代理因此不能完整到达 OpenTofu 等联网工具；直连不可用时，PVE `prepare-dependencies` 无法下载锁定的 provider。

## What Changes

- 将 `HTTP_PROXY/http_proxy`、`HTTPS_PROXY/https_proxy`、`NO_PROXY/no_proxy` 定义为独立于设施凭据的受控入口，统一大小写并拒绝冲突。
- 在 local、DinD 的 launcher → runtime → 实际联网子进程链路传递代理；runtime 单独调用时执行同一合同校验。
- 仅声明允许联网的操作使用代理，保留现有白名单、离线容器隔离、操作级文件与凭据选择；不从 Docker 默认配置隐式取得代理。
- 无配置仍直连；配置错误或代理故障明确失败，不尝试移除代理重跑，也不降低 TLS 校验。
- 支持无认证及 URL userinfo 提供 Basic 用户名/密码的 HTTP/HTTPS 代理；认证通过受控环境注入，不进入普通日志、错误输出、计划或摘要。
- 将代理变量列为保留名称，拒绝与 cloud-init 动态凭据通道冲突；明确环境代理支持路径，不将能力声明解释为所有 HTTP 客户端的代理保证。
- 用正式 launcher 在直连不可用、代理可用的隔离测试环境中验证锁定依赖下载、NO_PROXY、失败诊断及权限边界。

## Capabilities

### New Capabilities

- `runtime-network-proxy`: 标准变量入口、规范化、联网工具传递及失败/输出语义。

### Modified Capabilities

- `runtime-launcher`: local/DinD 受控传递、能力检查及隔离消费验收。

## Impact

预计涉及 Go launcher 的环境注入与 capability 校验、Python runtime 的环境构造/认证保护/错误报告、文档与定向测试。保留现有 provider 版本锁、checksum、归档校验和 `-backend=false` 准备路径；验收分别核对下载时 checksum、归档还原的成员/锁匹配及还原后原生初始化的 checksum。不调整镜像的 provider 打包方式，不改变 facility/state admission。

IaaS 负责代理合同和内部落实；调用方负责代理 endpoint、运行容器可达性、NO_PROXY 选择及测试网络。预计 S–M（1–3 天），范围为必要正确性和定向边界验证。本轮仅建立并校验 spec，未经后续实施指令不修改代码、不发布、不操作 ONE 或设施。
