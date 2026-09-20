## Context

`make test` 运行整个 pytest 集，`make check` 另外依赖显式环境和 OpenTofu 根目录。`tests/python` 中也存在子进程和工具集成测试，不能仅按目录宣称所有用例都是纯 Python。镜像冒烟已有独立入口。

## Goals / Non-Goals

目标是给出可靠、可度量的开发反馈入口，并保留完整检查集合。不建立自动影响选择服务，不根据 GitNexus 图裁剪最终验收，不改镜像发布/设备操作准入。

## Decisions

- 提供 `test-fast`（显式标记的纯离线用例）、`test-opnsense`、`test-pve`、`test-k3s`（现有 Python 模块测试集合）、`test-integration`（显式标记的本地工具集成）和 `check-fast`（test-fast、现有 typecheck、lint-imports）。后续 Python 质量 change 再接入 Ruff。
- 首批 fast 覆盖 common、新 conversion、性质测试及无需进程/设备的代表性领域逻辑。按实际执行行为标记，不承诺所有领域测试都属于 fast。未标记测试继续由普通 `pytest` 完整收集，不静默移出验收。
- `test-integration` 使用本地工具/临时目录/合成输入；真实设备操作继续走显式在线入口，镜像冒烟继续走 runtime-smoke。快速入口不读取环境库存、凭据，不启动 Ansible/OpenTofu/Docker 或网络探测。
- Make 入口显式定义集合，不接受任意 shell 命令拼接；可提供经过现有 shell 引用规则处理的 pytest 参数，但不将之作为在线开关。pytest 标记注册并严格检查拼写。
- `make test` 仍收集全体既有 Python/Ansible 测试，`make check` 仍是 CI 权威 gate。快速测试输出明确子集语义，空集合视作选择错误。
- 在同一机器、依赖环境和源码下记录完整/快速集合的收集数量和 `--durations` 耗时。性能记录标注冷热缓存和未执行范围；不预设虚构的提速比例，也不建立易抖动的固定秒数门禁。
- 首轮默认串行。只有实测慢点属于可隔离 CPU/进程任务，且并行重复运行结果一致、没有共享端口/文件/设备冲突时，才用 uv 加入 pytest-xdist dev 依赖并提供显式 workers 选项；不默认 `-n auto`，不并行设备测试。没有收益证据则记录后置，不影响本 change 完成。

## Risks / Trade-offs

- 子集误当完整通过 → 命名与输出明确范围，比较收集集合，CI 完整 gate 不变。
- 标记维护遗漏 → 未标记项仍进入全量测试；fast 使用显式选择，新增测试默认不自动获得 fast 资格。
- 并行不稳定 → 先串行落地并测量，再以代表性隔离测试决定是否启用并行。

## Migration Plan

前置 change 验收后确认本 change 的实现分支，建立耗时基线、增加入口和标记、验证集合边界、运行快速与相关集成检查。回退只涉及入口/测试配置，没有设备或数据迁移。

参考：[pytest-xdist 分发策略](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)。
