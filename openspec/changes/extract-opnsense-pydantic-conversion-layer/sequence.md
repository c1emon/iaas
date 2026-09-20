# 实施顺序

本序列按用户授权先设计、后依次实施。当前为设计阶段；下列任务均未实施。Git 分支及未提交文件的处理需要按 AGENTS.md 确认后才能进入 apply。

| 顺序 | Change | 前置 | 交付边界 |
| --- | --- | --- | --- |
| 1 | [extract-opnsense-pydantic-conversion-layer](proposal.md) | 无 | 七类转换层、Hypothesis 小型性质测试、Import Linter 依赖约束 |
| 2 | [add-fast-offline-validation-profiles](../add-fast-offline-validation-profiles/proposal.md) | 1 | 本地快速/模块/集成测试入口、可比较耗时，不削弱完整 gate |
| 3 | [extract-bounded-http-read-transport](../extract-bounded-http-read-transport/proposal.md) | 2 | 复用两处现有 HTTP 读取代码的预算、限流量、关闭响应和安全失败逻辑 |
| 4 | [standardize-safe-error-diagnostics](../standardize-safe-error-diagnostics/proposal.md) | 3 | 公共安全错误描述，接入转换、HTTP 与 PVE facade，保留领域状态 |
| 5 | [add-python-quality-gates](../add-python-quality-gates/proposal.md) | 4 | 范围受限的 Ruff 与严格 Pyright，接入快速/完整 gate |

各 change 通过自身任务、定向回归与严格 OpenSpec 检查后才进入下一项。顺序是实施依赖，不表示必须先发布镜像或操作设备。共同修改 `pyproject.toml`、锁文件、Makefile 和部分规格的 change 串行处理；后项以已完成前项为基线，归档时按此顺序同步规格，避免覆盖已有要求。

建议使用一个明确关联本序列的实现分支 `implement-iaas-quality-series`，保留当前未提交的设计文件；每项保留独立差异与验收结果。此分支方案只是待用户确认的选项，尚未创建/切换，也未自动暂存或提交现有内容。

默认实施仅包含源码、开发依赖和离线检查。无镜像发布、真实设备测试、全仓库格式化、所有领域 DTO 重写或完整平台资格矩阵。新增抽象以现有重复调用方为依据；阶段结果不宣称生产或真机验收。
