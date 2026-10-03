# 验证范围

实现分支：`fix/pve-template-check-action-dispatch`。以下为发布前的软件实现验证，仅修复 check 的输入及校验器分派，没有设施访问或修改 infra-ops；后续镜像发布结果见[交付记录](delivery.md)。

- 相关模板入口、cleanup、publisher、publication failures、请求合同、runtime dispatch、admission、acceptance：159 passed。
- acceptance plan、recovery runtime dispatch、recovery 及 recovery contracts：50 passed；既有 accept/recover 分派回归通过。
- `uv run pyright src/iaas/pve_template/runtime.py src/iaas/runtime_execution/selection.py`：0 errors、0 warnings。
- `openspec validate fix-pve-template-check-action-dispatch --strict --no-interactive`：通过。
- `git diff --check`：通过。GitNexus 完整重建后 `detect-changes --scope all --repo .` 识别 run/load_operation 等7个已跟踪符号、3条执行流程，risk=medium；不把重建前的无符号结果作为无影响证据。

新增反例覆盖默认/显式 publish、cleanup、retire 的有效及非法 TLS 输入、缺失/错误类型 action 输入、未知 action、无关输入与 CA 文件不可用。使用临时合成请求和禁止网络/删除的测试替身，检查 operation 的 network/state/infrastructure_write 均为 false。

上述是本地软件回归，不能证明模板9006已退役或现场最终验收已闭环；这些操作仍由调用方使用修复后的固定版本执行。
