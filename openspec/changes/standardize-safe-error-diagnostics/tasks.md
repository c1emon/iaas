## 1. 公共合同

- [ ] 1.1 确认前置验收与实现分支，分析 common/PVE/conversion/HTTP 异常调用关系；记录现有 message、except 与 status_code 兼容样例。
- [ ] 1.2 添加不可变 Diagnostic 和安全导出，保持旧 ValidationError 使用方式；测试代码/字段白名单、输入脱敏、不可变性及 CLI 前缀/退出码。

## 2. 首批接入

- [ ] 2.1 为 conversion 和 HTTP 既有失败附加 diagnostic，复用既有 reason 而不改变 observation 状态；通过非法输入/网络替身和原失败路径回归。
- [ ] 2.2 接入 PVE facade 的四类异常；用 SDK 替身验证固定代码、status_code、继承/捕获兼容、敏感消息脱敏与原 skip/warn/fail 判定。

## 3. 验收

- [ ] 3.1 运行 common、conversion、HTTP、PVE preflight/health 和 CLI 的定向离线测试及类型/导入检查；严格 OpenSpec、diff 和 GitNexus 检查通过，记录未迁移领域并保持公开结果 schema 不变。
