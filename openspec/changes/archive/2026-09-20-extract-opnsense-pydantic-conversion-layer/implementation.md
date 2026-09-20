# 实施记录

分支 `implement-iaas-quality-series` 经用户确认，从 `2ba6d9b` 创建并保留全部五个 change 的设计文件。

- Pydantic 2.13.5 / pydantic-core 2.46.5 锁定；Hypothesis、Import Linter 为 dev 依赖。Python 3.12 临时 runtime 环境 locked 安装及导入成功，确认两个 dev 工具未安装。
- common 布尔入口与 OPNsense 纯转换包落地，字段词汇单列 `schema.py`；reader 只保留兼容委托和领域校验，planning 直接依赖转换层。
- 来源别名先转换再比较；未知额外字段独立保留，动态字段名脱敏；普通配置错误保留身份/引用，必要引用错误失败关闭。网关观察统一布尔机制。
- 首轮 OPNsense Python + Ansible 回归：661 passed；补充性质/网关/依赖合同后，受影响 Python 回归：585 passed（含 Import Linter 合成违规用例）。现有 Pyright 0 errors。三组 Import Linter 合同通过，合成违规依赖分别被拒绝。
- 预编辑影响分析：flatten/normalize/semantic 为 CRITICAL，涉及 reader、plan、verify、reverse_documents、runtime/local；unknown 测试调用关系用实际 pytest 收集/源码确认。图索引的流程提取有全局截断提示，因此调用图仅用于定位，实际源码和回归为验收依据。
- 保留 defaults、排序和 absent 最小声明，现有 block/reject readback 不重跑 desired 授权。显式差异：0.0 布尔接纳；未知字段名使用固定分类，不输出动态 key。

补充完整集合基线：1339 collected，1337 passed / 2 failed，190.41s；两个失败均为 Make `check` 依赖顺序的文本保护断言。保留原依赖前缀后定向复跑 2 passed，不重复整个集合。VIP 复合地址双来源冲突补充回归后，conversion + reader 125 passed。

本阶段仅本机离线验证与 runtime 依赖安装检查；未构建或发布镜像，未访问或改写设备。

Luna/high 定向复核发现：活动确认把转换失败后缺失的 enabled 默认当启用。已将 flatten 默认改为拒绝配置转换错误，仅对象枚举显式允许 partial；networkgroup 活动读取安全降级。代表性回归覆盖该路径及 malformed 网络映射。最终 conversion + reader 126 passed，activation/recovery 12 passed；未扩大真机验收范围。

## 后续授权的实际只读测试与修复（2026-09-20）

用户随后授权实际只读测试，并要求测试、修复直到通过。首次实测虽然七类枚举均 complete，但 35 条 Filter 与 6 条 DNAT 的配置均变成 manual_required；这暴露了离线样例未覆盖的真实返回形态。

- Filter 原生 `statetimeout=""` 作为该字段的中性值保留；不放宽其他整数、null 或非默认 timeout。
- DNAT 仅消费空字符串 `address` 与 `%network` 展示字段，其他 address 形态、未知兄弟字段仍保留。依据官方 [DNat.xml](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/DNat.xml) 的 volatile address 定义，以及 [BaseField](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Base/FieldTypes/BaseField.php) 的百分号展示描述机制。
- `nordr` / `no_port_forward` 使用公共 Pydantic 布尔转换器；false 为标准 DNAT 的中性模式，true 仍不可表达，等价双来源通过、冲突及 `fasle` 继续拒绝。
- Luna/high 子 agent 分工修复、核对只读入口及原生字段语义；主 agent 复核并收紧空值范围，执行真实复测。没有为通过检查而丢弃未知配置，也没有把原生数据或凭据加入仓库测试。

最终源码实际联机 read 退出码 0，结果的 source identity 与最终源码一致：

| 资源 | 对象数 | 可表达 | manual_required |
| --- | ---: | ---: | ---: |
| aliases | 26 | 12 | 14 |
| filter-rules | 35 | 35 | 0 |
| dnat | 6 | 6 | 0 |
| gateways | 3 | 1 | 2 |
| interface-groups | 3 | 0 | 3 |
| vips | 6 | 6 | 0 |
| one-to-one-nat | 0 | 0 | 0 |
| 合计 | 79 | 60 | 19 |

七类均 complete、read_only=true，全部对象身份与标准配置均与重构前最后一次成功 read 记录一致。另对捕获的五类原生数据逐行比较重构前 reader.py 与当前 reader，标准配置结果一致；该离线对照使用当前依赖，不是旧镜像复验。19 个 manual_required 已核实为 14 个 internal/external Alias、2 个无可表达地址的网关、3 个空成员组，属于既定规格保留范围。

验证：首轮修复完整 `make test` 为 1388 passed（185.17s，1 个第三方 crypt 弃用警告）；完整测试启动后补充了 no_port_forward 等价布尔适配，最终源码的 conversion / reader / NAT lifecycle 定向回归 142 passed，Pyright 0 errors、4 组导入合同和 Ruff 通过。没有为最后这一字段调整重复整个测试集合。最终七类联机 read 使用的是包含该调整的源码。

一次复测在 1Password 授权阶段超时，未发出设备请求；重新授权后完成上述最终 read。私有原生响应、日志和汇总保存在本次 `/private/tmp/iaas-quality-live-read-*` 目录，仅脱敏样例进入源码。

严格 OpenSpec 与 diff 检查通过。预编辑转换入口 impact 为 CRITICAL；提交前变更分析覆盖 20 个符号、12 条流程，风险 HIGH，`partial=false`、`truncated=false`。常量和 pytest 入口的 UNKNOWN 关系通过实际引用及测试调用确认，未当作无影响。

本次验收为当前设备的只读枚举与配置转换；未执行设备写入、reload/reconfigure、活动状态检查、客户端业务验证或镜像发布。one-to-one-nat 现场为空，非空转换仍由离线样例覆盖，不宣称其非空真机验收。
