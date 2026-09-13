## Why

调用方需要将自身生成器产出的标准 OPNsense 资源声明交给 iaas 校验和执行。现有规则与 Alias 合同限定手写 YAML，部分反向匹配和别名上下文校验也不足，需要补齐这些通用合同，避免把具体运维策略编译器引入 iaas。

本 change 保留标识 `add-opnsense-selective-proxy-policy` 以维持已有引用；当前范围已收敛为通用声明输入与校验修正，旧名称不表示继续提供选择性分流能力。

## What Changes

- 规则与 Alias 接受调用方手写或确定性生成的标准期望声明；不限定生成器归属，不接受未经整理的设备导出作为直接部署源。Gateway/VIP 本次继续使用既有基础源，不扩展其来源合同。
- 补齐反向匹配的原生目标数量约束，并让离线校验与 Ansible 加载后的校验保持一致。
- 为已有入口自身网络保护提供明确的通用别名/接口网络上下文，按静态可证明范围校验；不把环境策略当作原生限制，不削弱已有保护。
- 保留稳定身份、显式 present/absent、增量管理、外部引用与保存/激活区分等现有合同。
- 从最终实现中移出选择性分流编译器、专用输入、策略测试与迁移阶段生成；这些由 infra-ops 的 `implement-opnsense-selective-proxy-routing` 承接。
- 复用现有校验、运行时及 Ansible 管理入口，不增加高层策略语言、专用运行时分支或任意写入透传。

## Capabilities

### New Capabilities

无。不在 iaas 新增选择性分流 capability；旧草案中的新增 spec 不进入主 specs。

### Modified Capabilities

- `opnsense-filter-rule-management`: 接受来源中立的标准期望规则声明，并明确反向匹配的通用安全校验。
- `opnsense-alias-management`: 接受调用方手写或确定性生成的标准 Alias 声明，保留显式对象管理与设备导出边界。
- `opnsense-mutation-input-validation`: 补齐原生匹配约束、通用校验上下文及 Python/Ansible 类型语义一致性。

## Impact

- 通用校验器、必要的 Ansible 适配、通用文档与代表性回归测试；不修改设备或调用方环境源。
- 当前工作树中 `opnsense_policy.py`、运行时的 `selective-proxy` 分支、专用文档和测试需要在后续实现阶段协调迁出；本轮只调整 change，不移动或删除代码。
- infra-ops 负责高层参数、分类/冲突语义、资源组合与迁移声明；iaas 只消费标准资源文件。调用方通过受支持接口使用 iaas，不依赖私有模块导入。
- 软件交付走既有版本流程；本 change 完成不表示已发布镜像、已部署或通过现场验收。调用方是否升级取决于所需通用合同是否已在固定版本中可用。
