## 1. 实施准备与依赖

- [x] 1.1 实施前检查工作树，按 AGENTS.md 获得实现分支选择后创建/切换；核对分支与工作树并重新运行相关符号的 GitNexus impact，记录高风险调用方。
- [x] 1.2 使用 uv 添加 Pydantic v2 项目依赖及 Hypothesis/Import Linter dev 依赖与锁文件；验证现有 Python 3.12、开发环境和 runtime 依赖组均可 locked 安装且 import 成功，测试工具不进入 runtime，不改 Collection 或安装 SDK。

## 2. 公共转换与错误边界

- [x] 2.1 实现可复用的内置布尔 TypeAdapter 入口与安全转换错误；分组测试真假等价表示、0.0/1.0、fasle/空/null/其他数值/空白/容器失败，确认没有自建 token 表或 truthiness。
- [x] 2.2 建立独立 OPNsense conversion 包、按来源转换与折叠别名、额外字段独立保留机制；验证依赖方向、无 I/O、输入不变，native-only/canonical-only/等价双来源/冲突双来源均无重复反转或 extra 覆盖，消费嵌套路径不丢未知兄弟字段，错误中 input/ctx/动态敏感 key 不泄漏。
- [x] 2.3 实现复用的 selector、字段限定列表及反向布尔组合类型；用字典/列表标识、重复/多选/非法 selected、CSV/成员映射和空值特例验证规则。

## 3. 七类资源迁移

- [x] 3.1 迁移 Alias 与 Filter 的转换、元数据分类及标准比较规范化；复用原生回归样例，验证内置 Alias 保留、URL-table 周期、CSV 端口/网络、字符串保真、未知 false/zero 和缺失字段行为。
- [x] 3.2 迁移 VIP、Gateway 与 Interface Group；用代表性样例验证反向标志、VIP 地址/前缀、空 gateway 原生身份、空 members 不可表达及 nogroup 空值行为。
- [x] 3.3 迁移 DNAT 与 1:1 NAT；验证协议/端口规范形式、嵌套别名与原生字段冲突、既有不支持模式，以及最小删除声明不被补齐 present 字段。

## 4. 调用方接入与回归

- [x] 4.1 接入 reader 配置/身份/引用所需解码与既有状态观察调用方；删除已迁移 helper 的重复实现，必要兼容入口仅委托；验证普通配置字段失败仍保留身份/引用，阻止删除被引用 Alias 且不阻断无关计划，selector/身份/必要引用失败仍 incomplete，完整不可表达对象仍 manual_required。
- [x] 4.2 将 reader 网关 route_required 与 gateway_checks 的 _configured_monitor/_route_check 接入相同 monitor 标志转换，删除 native_false 集合及独立 _bool token 表；分组验证 read/可选状态观察对 0/"0"/False/"No"/"off" 的路由读取与检查语义一致，缺失/fasle/外围空白维持 unknown 而非 not_applicable，默认路径不新增深度检查。
- [x] 4.3 将 planning、verify、recovery 的比较规范化接入相同入口；对七类代表样例比较既有配置输出，验证默认值/排序/候选字段稳定、恢复基于实际 before-state，已有 block/reject 观察不重跑 desired 准入、标准声明仍严格拒绝非法类型。
- [x] 4.4 运行受影响 OPNsense Python 测试、写入准入相关 Ansible 测试和既有类型检查；确认离线默认执行不需要设备、凭据或发布镜像，记录实际覆盖与限制。

## 5. 性质测试与依赖约束

- [x] 5.1 添加规范化幂等、输入不变、别名一致性和错误脱敏的有界 Hypothesis 测试；验证通过且典型反例能失败，失败可重放，保留现有固定样例。
- [x] 5.2 添加三组 Import Linter 合同与 `make lint-imports`，接入 `check`；验证现有依赖通过、临时合成违规依赖被拒绝，更新本地检查说明。

## 6. 阶段收尾

- [x] 6.1 在性质测试和依赖约束也接入后，复核全部定向测试、依赖锁定、运行时打包检查、源码差异和 GitNexus detect_changes；检查无重复转换路径、原始错误输出或无意合同变更，更新 change 的实施状态。发布与新的设备测试不在本任务范围。
