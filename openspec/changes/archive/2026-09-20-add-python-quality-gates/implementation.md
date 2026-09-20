# 实施记录

前四阶段提交后，在 `implement-iaas-quality-series` 实施。主 agent 接入工具与公共模块类型守卫；Luna/high 子 agent 分别完成 conversion 类型修订和独立门禁探针。

- Ruff 0.16.8 经 uv 加入 dev 并锁定。固定 `E4/E7/E9/F` 规则覆盖 14 个文件（9 个核心源码、5 个测试文件）；不执行 fix、formatter 或全仓风格迁移。
- Pyright 1.1.411 仅对 common 转换/诊断、OPNsense conversion、HTTP transport 共 9 个源码文件启用 strict；其余目录保留原检查模式，vendored collections 继续排除。
- schema 跨模块常量通过 GitNexus rename 改为公共名称并补齐类型。复用 Pydantic TypeAdapter 明确已有 dict/list 边界，保留原类型接纳与错误分类；runtime 类型守卫只使用附理由的单行 `reportUnnecessaryIsInstance` 豁免，无模块级关闭或 cast 到 Any。
- `lint-python` 加入 `check-fast` 和完整 `check`，保留完整入口原依赖前缀。新增 HTTP 纯测试进入 fast 集合，完整 pytest 收集仍为 1386 项。
- 最终 `make check-fast` 成功：206 passed / 1180 deselected，pytest 用时 0.52s（本机已有依赖和缓存，非整条命令耗时）；完整配置 Pyright 0 errors、4 组 import contracts kept、Ruff 通过。conversion + reader 定向回归 126 passed。
- 独立临时探针确认 Ruff 未定义名 F821 与 Pyright 错误返回类型均以退出码 1 拒绝；探针已移除。locked runtime dry-run 和独立 Python 3.12 runtime 安装确认 Ruff 不在运行依赖中。
- GitNexus upstream 仍显示转换入口 CRITICAL，涉及 reader、plan、verify 的已有调用链；常量属性关系为 UNKNOWN，补充源码引用确认。没有将图中的未知关系当作无影响。
- 五项 change 的严格 OpenSpec 校验与 diff 检查通过；提交前 GitNexus 变更分析覆盖 43 个符号、20 条流程，风险 CRITICAL，`partial=false`、`truncated=false`。风险对应上述既有转换调用链，已做定向回归。

本阶段未重跑完整 pytest 或需要环境 fixture 的完整 `make check`；序列的完整 pytest 基线及两个失败的修复复验记录见第一阶段 implementation.md。结果限定为本机离线检查，不代表设备、客户端路径、镜像发布或全仓严格类型验收。后续扩展检查范围按实际改动需要推进。
