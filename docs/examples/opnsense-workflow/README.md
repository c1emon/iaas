# Synthetic OPNsense workflow

这些文件只用于检查 runtime 的文件选择、请求选择和候选上下文，不代表真实
设备、API 凭据或现场策略。`inventory.yml` 使用文档保留地址，不能直接用于
连接设备。

从仓库根目录执行离线检查：

```sh
PYTHONPATH=src uv run python -m iaas.runtime_execution \
  --environment "$PWD/docs/examples/opnsense-workflow/environment.yml" \
  --component opnsense --operation plan --scope firewall \
  --output /tmp/opnsense-workflow-plan --discover
```

完整 `plan` 需要在线读取 OPNsense，因此此命令的 `--discover` 阶段只验证
输入闭包；没有注入 API 凭据时不会运行设备操作。实际调用应由 launcher 注入
`OPNSENSE_API_KEY` 和 `OPNSENSE_API_SECRET`，并使用新的 output 目录保存候选。
`candidate.json` 生成后，调用方应保存其 SHA-256，并以同一个候选、目标和执行
身份进入 apply。apply 的 `execution_id` 必须同时作为 output 目录 basename。

迁移时保留 request v1 和 launcher `interface_version` v1；新运行时生成的
`candidate`、`result` 和 `recovery` 是 workflow schema v3。v1/v2 候选不会由 apply/verify
静默升级，必须重新 plan；旧恢复材料应保留，核对原执行和当前状态后准备新的显式方案。
默认以配置回读
匹配与原生激活成功作为通过条件，不探测精确固件版本，不要求 PF/内核运行态证明。
Alias、Gateway 和接口组每次实际激活都会向 stderr 与 result 写入不可关闭的
`IAAS-OPNSENSE-RESULT-LIMITATION` 提醒；明确失败仍会停止后续阶段。
动态 Alias 的缓存、刷新和加载交给设备原生机制，结果不声称独立验证了内部步骤。
独立 `verify` 仅核对已保存配置，不追认历史动作。

`read` 默认隐藏已确认不能独立管理的系统内置／派生对象详情，未知来源、未知管理能力
和普通配置转换失败仍可见。环境的 `components.opnsense.options.include_system: true`
可展开当前选择范围内的系统项；该布尔选项仅用于 read。本地开发命令对应
`python -m iaas.opnsense_workflow.local read ... --include-system`。
完整观察保存在 `diagnostics/observations.json`，`result.json` 中的读取视图带有
`observation_scope: display`，不能当作计划、漂移或缺失判断的完整状态输入。
打开开关不扩大管理权限，也不提供完整 PF 活动规则集。


本目录还提供实际合同生成的合成材料：

- [candidate.json](candidate.json)：固定声明、选择、目标、虚构 runtime digest、现场空集合与阶段。
- [result.json](result.json)：测试替身返回原生成功、配置回读一致，结果为 `fully_verified`，验证范围为 `saved_configuration`，包含 Alias 提醒。
- [recovery.json](recovery.json)：写前不存在标记和测试替身的可确认后态。
- [recovery-request.yml](recovery-request.yml) 与 [reverse-candidate.json](reverse-candidate.json)：
  从上述 recovery 生成新的删除候选；没有执行回滚。

成功示例使用合成适配器演示编排和恢复合同，不证明上游内部步骤或实际运行态。
这些 JSON 来自离线测试替身，不可当作设备执行证据或直接用于真实 apply。
真实恢复需在环境的 `files` 指定 inventory、request、recovery，移除 desired inputs；
运行 plan 得到新候选后重新审查，再以新的执行身份及激活检查结论 apply。
未知后态、后续漂移或 `manual_required` 会拒绝自动恢复。示例里的肯定检查结论
只是软件输入；真实调用方必须先完成共享激活检查并保持串行化。

需要进一步诊断时，使用真实 inventory、候选和环境变量凭据运行只读检查：

```sh
PYTHONPATH=src uv run python -m iaas.opnsense_workflow.inspect \
  --inventory /path/to/inventory.yml --candidate /path/to/candidate.json \
  --output /path/to/new-inspection.json
```

该工具复用已有 PF、成员和路由检查；精确版本限制仅影响相应诊断能力。
报告是当前运行态观察，不是历史动作或业务验收证明。退出码 `0` 表示匹配或不适用，
`1` 表示不匹配，`2` 表示未知、不支持或检查不完整；不改变默认 apply 的结果。
