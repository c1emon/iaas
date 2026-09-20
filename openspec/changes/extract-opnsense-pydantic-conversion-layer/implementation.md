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
