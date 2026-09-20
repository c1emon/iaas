# 范围受限的 Python 质量门禁

状态：已实施；验收范围见本 change 的 `implementation.md`，本阶段提交在当前收尾流程完成。序列第 5 项，前置 `standardize-safe-error-diagnostics`。本 change 未归档，不代表全仓严格验证、镜像、设备或生产验收。

## Why

仓库已有 Pyright 和 Ansible/YAML 校验，但新增纯转换与 transport 代码适合用统一 Python lint 和更严格的类型检查保护。以明确模块范围接入可以提前发现错误，避免全仓格式调整淹没功能差异。

## What Changes

- 使用 uv 添加 Ruff dev 依赖，为本序列新增/调整的纯 Python 边界建立明确检查范围。
- 在新 conversion、http_transport 和新公共转换/诊断文件上启用局部严格 Pyright；其余模块保留现有模式。
- 新增只检查、不自动修改的 `lint-python`，接入 check-fast 与完整 check；不全仓格式化或大面积补注解。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `iaas-validation-entrypoints`: 增加范围明确的 Python lint 与严格类型 gate，保持离线和非修改语义。

## Impact

涉及 pyproject/uv.lock、pyrightconfig、Makefile、选定模块与门禁测试。Ruff 仅 dev 使用，不增加运行镜像工具或改变业务结果。
