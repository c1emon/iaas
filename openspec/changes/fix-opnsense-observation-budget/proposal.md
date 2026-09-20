# 修复 OPNsense 观察预算作用域

## Why

rc.10 实测复现同一 reader 跨轮累计响应字节，第五轮观察超过 8 MiB。多阶段 apply 的漂移检查、验证和失败恢复回读复用 reader，因而可能在正常单轮响应大小下耗尽预算。原执行未记录逐调用字节数，不能把独立诊断的轮次当作原始执行轨迹。

## What Changes

- 将 workflow 的累计字节预算限定到一轮完整观察，轮内资源、分页、详情和嵌套读取共享预算；下一轮重新计数。
- 配置读取、主动状态检查和关联完成观察使用明确边界，保留共享时间 deadline、单响应限制和失败语义。
- 验证多阶段 apply 与失败后的 recovery 回读；不完整观察仍为 unknown，不沿用旧后态冒充最终确认。

## Capabilities

### Modified Capabilities

- `bounded-http-read-transport`: 明确 OPNsense workflow 调用方的累计预算作用域。

## Non-goals

不增加 Alias、Gateway、Interface Group 的可表达范围，不修改写入器、自动重试、恢复准入或公共结果格式，不发布镜像。用户随后授权在新的已确认窗口进行本地源码设备写入测试，限独立测试 Alias、禁用 Filter 及其恢复清理。

后续授权的根因诊断仅为激活失败材料增加安全分类，并审阅执行零配置改动的激活恢复候选；该诊断不改变原成功判断。

## Impact

涉及 workflow reader、完成观察边界、定向离线测试和开发验证文档。通用 HTTP helper 及独立 diagnostics 的操作预算保持不变。
