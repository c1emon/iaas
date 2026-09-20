# 实施顺序

本序列按用户授权先设计、后依次实施，五项实现与离线验收均已完成，按阶段提交。后续授权的联机只读复验及修复已完成，见第一项 implementation.md；未执行设备写入、镜像发布或全仓严格验证。

| 顺序 | Change | 前置 | 交付边界 | 当前状态 |
| --- | --- | --- | --- | --- |
| 1 | [extract-opnsense-pydantic-conversion-layer](proposal.md) | 无 | 七类转换层、Hypothesis 小型性质测试、Import Linter 依赖约束 | 已提交 `aeac3be`，只读回归修复 `4205d92` |
| 2 | [add-fast-offline-validation-profiles](../2026-09-20-add-fast-offline-validation-profiles/proposal.md) | 1 | 本地快速/模块/集成测试入口、可比较耗时，不削弱完整 gate | 已提交 `18c9414` |
| 3 | [extract-bounded-http-read-transport](../2026-09-20-extract-bounded-http-read-transport/proposal.md) | 2 | 复用两处现有 HTTP 读取代码的预算、限流量、关闭响应和安全失败逻辑 | 已提交 `c82e1f1` |
| 4 | [standardize-safe-error-diagnostics](../2026-09-20-standardize-safe-error-diagnostics/proposal.md) | 3 | 公共安全错误描述，接入转换、HTTP 与 PVE facade，保留领域状态 | 已提交 `88caa66` |
| 5 | [add-python-quality-gates](../2026-09-20-add-python-quality-gates/proposal.md) | 4 | 范围受限的 Ruff 与严格 Pyright，接入快速/完整 gate | 已提交 `719be12`，见 [implementation.md](../2026-09-20-add-python-quality-gates/implementation.md) |

各 change 通过自身任务、定向回归与严格 OpenSpec 检查后才进入下一项。顺序是实施依赖，不表示必须先发布镜像或操作设备。共同修改 `pyproject.toml`、锁文件、Makefile 和部分规格的 change 串行处理；后项以已完成前项为基线，归档时按此顺序同步规格，避免覆盖已有要求。

本序列使用实现分支 `implement-iaas-quality-series`，各阶段保留独立提交与验收结果。阶段 5 的验收记录见对应 `implementation.md`；这五项 change 已于 2026-09-20 按上表顺序归档并同步主规格。

初始实施包含源码、开发依赖和离线检查；后续已授权并完成真实设备只读测试。无镜像发布、设备写入、全仓库格式化、所有领域 DTO 重写或完整平台资格矩阵。新增抽象以现有重复调用方为依据；阶段结果不宣称生产、设备写入或业务验收。
