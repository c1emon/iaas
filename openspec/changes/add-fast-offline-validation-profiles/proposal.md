# 本地离线验证反馈提速

状态：已实施，提交 `18c9414`；验收范围见本 change 的 `implementation.md`。序列第 2 项，前置 `extract-opnsense-pydantic-conversion-layer`；见其 [sequence.md](../extract-opnsense-pydantic-conversion-layer/sequence.md)。本 change 未归档，不代表镜像、设备或生产验收。

## Why

现有 `make check` 聚合 Python、生成物、Ansible 和 OpenTofu 校验，适合作为完整 gate，但日常局部修改缺少稳定的快速入口。让开发者先运行小范围相关检查，并保留完整验收，可以减少对镜像构建与发布的依赖。

## What Changes

- 增加环境无关的快速 Python 检查、模块测试和外部工具集成测试入口，明确覆盖范围。
- 保留 `make test` 和 `make check` 的完整集合，快速入口不替代 CI 完整 gate。
- 记录可比较的本地耗时与收集数量；只有测量证明收益且用例隔离满足要求时才接入可选并行。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `iaas-validation-entrypoints`: 明确快速/模块/集成检查入口、覆盖边界与完整 gate 保留。

## Impact

修改 Makefile、pytest 标记配置、选定测试标记和验证说明；后续质量工具可接入快速入口。默认不改 CI 架构矩阵，不发布镜像、不需要设备或运行凭据。
