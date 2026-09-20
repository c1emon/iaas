## 1. 工具与范围

- [x] 1.1 确认前置验收、实现分支与源码范围，使用 uv 添加 Ruff dev 依赖；验证锁定安装且 runtime 安装不包含 Ruff。
- [x] 1.2 配置固定 Ruff 路径/规则与 Pyright 严格路径；核对 vendored/生成物排除及范围外旧模式保留。

## 2. 接入与必要修订

- [x] 2.1 添加 lint-python 并接入 check-fast/check；验证临时 lint/type 违规会失败、检查不修改文件且无需环境或凭据。
- [x] 2.2 对选定模块作必要的 lint/类型修订，编辑前 impact；运行静态检查和功能回归，确认无宽泛 ignore 或全仓格式化。

## 3. 验收

- [x] 3.1 更新质量检查说明，运行 fast、完整类型/导入检查和受影响测试；严格 OpenSpec、diff 和 GitNexus 变更分析通过，记录固定覆盖范围与后置项。
