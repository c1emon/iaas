# 设计复核记录

日期：2026-09-19。范围：需求和 OpenSpec 设计；未实施、未发布、未操作设备。

## 收敛结果

- 需求修订明确：共享 reload 的授权边界、候选与现场有效状态、部分部署基线归属、写前实际状态恢复、现有 diagnose 覆盖和激活确认限制。
- 执行语义与仓库边界两路独立复核确认需求无剩余阻断。
- OpenSpec 三路独立复核发现并关闭两项：read 不得依赖候选；恢复材料必须自包含执行身份、尝试阶段和可确认后态。
- 最后一轮三路复核均确认无新增阻断。结论限于设计一致性，不代表实现可用或现场资格。

## 边界与覆盖

- 新增 1 个通用 workflow capability，修改 4 个既有 capability；NAT/DNAT/Groups 对 launcher apply、必要依赖读取及资源排序的旧限制已通过 delta 明确调整。
- 调用方策略编译、业务迁移、所有权元数据、部署基线与 `--previous` 均未进入本仓库实现任务。
- 既有 schema、身份、资源类型与直接 Ansible 入口保留；无 PVE state、站点默认值、锁服务或证据平台扩展。
- 全部 19 项实施任务保持未勾选；开始实施须另行满足分支与授权规则。

## 文档验证

- `openspec validate add-opnsense-config-workflow --strict` 通过；proposal、design、specs、tasks 四类规划产物完整。
- 7 个 MODIFIED requirement 对照现有规范名称有效，16 个原有 scenario 名称全部保留。
- 本地 Markdown 链接与新增/修订文档空白检查通过。未运行代码测试或设备调用；此轮没有代码变更。
