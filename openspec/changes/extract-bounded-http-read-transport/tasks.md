## 1. 边界与 helper

- [ ] 1.1 确认前置验收、实现分支和工作树，运行两个适配器的 GitNexus impact；冻结当前 endpoint/TLS/timeout/字节限制和公共 reason/status 映射作为对照。
- [ ] 1.2 实现 http_transport 的有限预算、一次请求和安全失败；fake session/clock 测试验证请求参数、无 redirect/retry、累计字节不重置、所有已获得响应均关闭。

## 2. 接入

- [ ] 2.1 将 workflow reader._request 委托给 helper，保留预算作用域及领域映射；运行 confirmation budget、reader 与本地入口相关回归。
- [ ] 2.2 将 diagnostics.Transport.call 委托给 helper，保持只读 endpoint 白名单和状态；运行诊断 fixture/入口测试，覆盖 HTTP 与 stream 失败、空响应和错误脱敏。
- [ ] 2.3 更新 import contracts 保证 http_transport 不导入领域、纯 conversion/validation 不导入 transport；验证合同与 helper 的依赖方向。

## 3. 验收

- [ ] 3.1 运行受影响离线测试、typecheck、lint-imports 和严格 OpenSpec；检查源码/detect_changes，记录已验证预算边界及慢流限制，确认写入器及请求范围无变化。
