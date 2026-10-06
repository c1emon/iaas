# OPNsense audit 元数据读取修复

rc.35 的 filter rule、DNAT 原生响应携带非空 `audit` 时，读取结果的标准配置为 null，选中对象因此无法通过 planner。现场只复现读取，未运行完整 plan/apply。交接来源：infra-ops 的 `docs/operations/iaas-lifecycle-acceptance-findings.md`。

修复在 filter rule、DNAT、one-to-one NAT 的资源元数据清单中识别 `audit`。依据 OPNsense 当前 [Filter](https://github.com/opnsense/core/blob/master/src/opnsense/mvc/app/models/OPNsense/Firewall/Filter.xml) 与 [DNat](https://github.com/opnsense/core/blob/master/src/opnsense/mvc/app/models/OPNsense/Firewall/DNat.xml) 模型中的 `JsonAuditField`。26.7.3 的模型尚无该字段；本修复消费现场已确认、当前模型定义的读取元数据，不扩大现有 activation 固件准入。标准配置、观察输出、计划及展示投影均不携带审计身份；其他未知实质配置仍拒绝重建与计划。没有全局忽略 `audit`。

全部 7 类资源的模型核对还发现 one-to-one NAT 的 `sort_order`、`prio_group` 显示排序字段遗漏，以及 VIP 的 `vhid_txt` 派生显示字段遗漏。前两者在 [26.7.3 Filter 模型](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Firewall/Filter.xml) 已标为 volatile；后者由 [VipField](https://github.com/opnsense/core/blob/26.7.3/src/opnsense/mvc/app/models/OPNsense/Interfaces/FieldTypes/VipField.php) 根据实际 VHID 派生。只识别这些明确字段，不忽略 category、VHID、sequence 等实质配置，也不把所有 volatile 字段自动视为无关。

| 资源 | 同类检查结论 |
| --- | --- |
| filter rule、DNAT | audit 现场复现，本次修复 |
| one-to-one NAT | audit 及排序元数据存在源码与合成样本复现，无新增现场证据，本次修复 |
| VIP | vhid_txt 非空合成样本复现，现场 6 个 VIP 原已完整表达，本次补齐明确派生字段 |
| aliases、gateways、interface groups | 已核对模型未发现 audit 或遗漏的同类纯元数据；没有全量真实设备验证结论 |

## 软件验证

`UV_CACHE_DIR=/private/tmp/iaas-uv-cache uv run pytest -q tests/python/test_opnsense_audit_metadata.py`：12 个代表性用例通过。各新增识别字段的正例均先复现失败；修复后完整观察与基线相同，审计信息变化仍生成同一个 unchanged 计划。未知实质字段阻断计划；未授权资源上的 audit 仍阻断。仅使用合成 Collection 响应，未访问或修改设备。

完整 OPNsense 离线回归 678 个用例通过；Ruff、Pyright（0 errors）、OpenSpec strict 校验及 `make check-runtime-contracts`（实际 runtime capabilities 与 launcher 集成）通过。最初沙箱内 3 个 Ansible 集成用例被临时目录或本地 RPC 权限阻止，沙箱外复跑及最终完整回归均通过。

## infra-ops 升级复验

配套发布使用下一固定版本 `v0.1.0-rc.36`，runtime 为 `ghcr.io/c1emon/iaas-runtime`；launcher 使用同一 release 的平台二进制与 `SHA256SUMS`。发布成功须以 [OCI release workflow](https://github.com/c1emon/iaas/actions/workflows/oci-release.yml) 的构建、发布及两种匿名消费检查结果为准，固定实际发布的 manifest digest。本文不据版本预留宣称镜像已交付。

升级后先重做完整只读准备，核对 managed 身份、filter rule / DNAT 标准配置及业务差异。审计信息不应成为差异。确认完整性后，由 infra-ops 承接正式部署基线、目标门禁、新计划与审批；本修复不替调用方初始化基线或开放 apply。现场 plan/apply 和设施验收仍由该次复验建立证据。
