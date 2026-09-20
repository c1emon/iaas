## 1. 基线与分类

- [x] 1.1 确认前置 change 验收、分支和工作树；核对 Make/pytest 调用关系，记录当前完整测试收集集合及一次可比较耗时基线。
- [x] 1.2 注册 fast/integration 标记并标注首批代表用例；通过 collection-only 对比验证完整集合不减少、fast 不包含工具/设备依赖且非空。

## 2. 入口与反馈

- [x] 2.1 实现 test-fast、test-opnsense、test-pve、test-k3s、test-integration 和 check-fast；检查实际命令、错误退出传播及无环境/无凭据执行。
- [x] 2.2 在相同环境测量 fast 与完整入口，记录范围和耗时；仅有证据时增加可选 xdist workers 并验证无共享资源冲突，否则记录后置理由。

## 3. 验收

- [x] 3.1 运行快速、受影响模块和代表性工具集成检查，核对 CI 仍使用完整 gate；通过测试证明未知 marker/空选择报错。
- [x] 3.2 更新验证说明和实施结果，运行严格 OpenSpec、GitNexus 变更分析及 diff 检查后结束本阶段。
