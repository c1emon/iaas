# Synthetic OPNsense workflow

这些文件只用于检查 runtime 的文件选择、请求选择和候选上下文，不代表真实
设备、API 凭据或现场策略。`inventory.yml` 使用文档保留地址，不能直接用于
连接设备。

从仓库根目录执行离线检查：

```sh
PYTHONPATH=automation/src uv run python -m iaas_automation.runtime_execution \
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
`candidate`、`result` 和 `recovery` 是 workflow schema v2。旧材料不会由 apply/verify
静默升级，必须重新 plan。实际消费前先通过只读版本闸门确认 OPNsense 26.7.3；版本
无法确认或不匹配时，待执行阶段在首写前阻塞。即使版本匹配，Alias、Gateway 和
Firewall Group 仍缺少必要完成证据。静态 Alias 的活动成员匹配只说明当前状态，
不能提升 activation；`verify` 只
检查当前状态，也不追认历史动作。动态内容只按设备原生处理/加载语义执行；没有
来源、有效期和所有权证据的缓存不得复用。


本目录还提供实际合同生成的合成材料：

- [candidate.json](candidate.json)：固定声明、选择、目标、虚构 runtime digest、现场空集合与阶段。
- [blocked-candidate.json](blocked-candidate.json)：按当前源码能力边界生成的阻塞示例，Alias 缺少动作完成证据，整批零写入。
- [result.json](result.json)：测试替身确认保存/激活，活动态不支持，结果为 `completed_with_unverified`。
- [recovery.json](recovery.json)：写前不存在标记和测试替身的可确认后态。
- [recovery-request.yml](recovery-request.yml) 与 [reverse-candidate.json](reverse-candidate.json)：
  从上述 recovery 生成新的删除候选；没有执行回滚。

成功示例使用能返回动作完成证据的合成适配器，超出了当前真实 Alias API 的能力，
用于演示编排和恢复合同；真实支持边界见 blocked 示例。
这些 JSON 来自离线测试替身，不可当作设备执行证据或直接用于真实 apply。
真实恢复需在环境的 `files` 指定 inventory、request、recovery，移除 desired inputs；
运行 plan 得到新候选后重新审查，再以新的执行身份及激活检查结论 apply。
未知后态、后续漂移或 `manual_required` 会拒绝自动恢复。示例里的肯定检查结论
只是软件输入；真实调用方必须先完成共享激活检查并保持串行化。
