# 实施记录

## 当前范围调整（2026-09-14）

用户明确要求 SNAT 暂缓、保留位置，待上游修复后再做。本轮继续 DNAT、1:1 NAT、Groups；下文四资源统一阻塞结论是范围调整前的历史记录，不再以 SNAT 阻断剩余三资源。

预留 `manage-snat.yml`、`snat.yml`、`opnsense_snat_rules` 和源路径变量 `opnsense_snat_source`。占位入口在读取源文件、凭据和设备之前明确失败，不注册可用 SNAT validator/runtime resource，不改变旧四文件目录校验。普通执行和 check mode 均已验证明确提示未实现，changed=0；两份新增 YAML 的 yamllint 通过。这里完成的是位置预留，SNAT 功能仍延期。

剩余三资源已完成读取路径源码审查：DNAT 使用 `DNat.rule`、1:1 使用 `filter.onetoone.rule`、Groups 使用 `group.ifgroupentry`；1:1 没有 SNAT 的 getAction 覆盖。DNAT 的 associated_rule=rule 在 filter reload 时临时生成关联规则，没有独立持久 UUID；切换、禁用、删除后在下次 apply 消失。依据为 26.7 的各控制器、ApiMutableModelControllerBase、filter.lib.inc 和 ForwardRule.php，未进行设备验证。

依赖阶段：开发与 OCI 的 Collection 清单均固定 Git 源 `1423500c29f88da9ba8147a23fc64006cf464159`，本地实际安装成功。OCI 安装时使用 Git，随后卸载，不在运行时下载或升级。候选自身仍标记版本 26.1.11，DNAT 为 unstable，不能用版本字符串代替源码 SHA。67 项既有 CI/OPNsense 校验、上下文、提供者及恢复测试通过；新增三项真实模块 check mode 创建预测测试通过，外部会话替换为无写测试替身。未构建或发布镜像，不宣称现场通过。

以下为范围调整前的准入及阻塞历史，用于保留延期原因。

## 实施准入（2026-09-14）

- 用户已明确授权持续实施和阶段提交。开始时位于 `add-opnsense-dnat-management`，HEAD 为 `c2ba443`，工作树干净；未创建或切换分支。
- 本轮只修改 iaas 的通用能力；infra-ops 负责站点声明、迁移、设备窗口和恢复。不会自动发布镜像或部署设备。
- 使用全局 `gitnexus analyze` 刷新索引至当前源码。生成的 AGENTS.md 更新随阶段提交保留。索引报告流程枚举截断，因此未列出流程不能作为不受影响的依据。
- `gitnexus impact validate_document --direction upstream`：CRITICAL，13 个对象，3 个直接调用，9 条流程，4 个模块。调用覆盖文件/目录校验、runtime 生成和执行链路。
- `gitnexus impact compile_documents --direction upstream`：CRITICAL，8 个对象，6 个直接调用，6 条流程，2 个模块。已向用户提示两项风险；后续以显式资源接入及原四类回归约束共享修改。
- 基线：`uv run pytest -q tests/python/test_opnsense_validation.py tests/python/test_opnsense_resource_context.py tests/python/test_opnsense_provider_admission.py`，52 passed。该结果使用当前 26.1.11 依赖，不代表新候选依赖或设备验收通过。

## 候选依赖审查

- 候选完整 SHA：`1423500c29f88da9ba8147a23fc64006cf464159`（DNAT PR #430）；26.1.11 tag 为 `7de29c528f9326b10ba74184e64a214d961c4811`。
- 相对 26.1.11 共 16 个文件变化，595 行增加、8 行删除；`plugins/module_utils/base`、`helper`、`defaults` 无变化。新增 DNAT 模块及 list/reload 分派；另有 dnsmasq 与文档/测试变动。未安装或切换生产依赖。
- 最小离线探针加载四个真实模块，并调用固定源码的请求/响应转换：SNAT target_port、DNAT local_port、Groups description 的显式 null 输出为空字符串；SNAT nonat / DNAT nordr 归一化为 no_nat / no_port_forward 布尔值；DNAT disabled 与 Groups nogroup 的反向输出通过。这只证明模块加载及转换，不证明设备行为或完整生命周期。
- 复现命令：`uv run python openspec/changes/add-opnsense-dnat-management/provider_probe.py /path/to/ansible-opnsense-checkout`。checkout 必须固定到上述候选 SHA。输出四条转换通过、两条 reload 目标拒绝和 SNAT 26.7 读取失败复现；不读取凭据、不访问设备。

## Groups 集成缺口（可由现有提供者能力接入）

固定候选的 [`reload.py`](https://github.com/O-X-L/ansible-opnsense/blob/1423500c29f88da9ba8147a23fc64006cf464159/plugins/modules/reload.py) 没有 `group` / `rule_interface_group` target。探针调用真实 `run_module()` 与 Ansible 参数解析，两者均在网络调用之前因不在 choices 中而失败。上游当前 HEAD `4f4acafcb5b6bd21886645e3ab0c530d8f0b25f1` 同样未提供该目标，不能简单改用当前上游提交解决。

`Group` 本身通过 `BaseLogic._base_reload` 调用 `firewall/group/reconfigure`，但 CRUD wrapper 只在该项 changed 且 reload=true 时执行。逐项 reload=false 后没有独立受支持的 Groups 激活目标，无法实现本 change 要求的整批成功一次激活，以及无变更重试时的强制恢复。

原生 [GroupController](https://github.com/opnsense/core/blob/stable/26.7/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/GroupController.php) 提供 reconfigure，执行接口注册和 `filter reload skip_alias`，并在删除时使用 whereUsed 保护。问题是 Collection 的公开独立入口缺失，而非设备没有该 API；使用普通 rule reload 不能替代接口注册。

固定 Collection 自带 `raw` 模块可以对固定的 `firewall/group/reconfigure` 执行 POST，并在 check mode 下跳过 POST。该限定调用不需要 fork 或私有客户端，可以作为后续 Groups 批量激活实现方式；不向调用方暴露任意 API 参数。这里只记录源码可行路径，尚未完成其批量/恢复测试。Groups reload target 缺失本身不作为本次停工的硬阻塞。

## 已确认硬阻塞：SNAT 26.7 读取 API 不兼容

原生 [SourceNatController::getAction](https://github.com/opnsense/core/blob/stable/26.7/src/opnsense/mvc/app/controllers/OPNsense/Firewall/Api/SourceNatController.php) 只返回 `filter.general`；候选 `SNat` 却仍使用 `source_nat/get` 和 `API_KEY_PATH=filter.snatrules.rule`。探针向真实 `SNat.get_existing()` 提供该原生响应形状，稳定复现 `Got invalid API_KEY_PATH: 'filter.snatrules.rule'`；automatic、hybrid、advanced、disabled 四种模式均失败。因此前述字段转换通过不能证明真实列举入口兼容。

原生 `search_rule` 才列举规则，且只在 hybrid/advanced 模式返回手工规则；automatic/disabled 模式不能据其空结果断言指定手工规则不存在。不能只替换 endpoint 就宣称实现了安全的精确增量管理，也不能为此自动切换出站 NAT 模式。

上游 [issue #446](https://github.com/O-X-L/ansible-opnsense/issues/446) 记录相同问题。当前上游 HEAD `4f4acafcb5b6bd21886645e3ab0c530d8f0b25f1` 的 `nat_source.py` 仍使用相同 search/path，升级到该提交不能解决。这里是正式资源模块的读取/存在性检查不兼容，修复需要提供者变更；不能以局部 raw 调用替换整个 SNAT 资源客户端。

继续条件：获得含 SNAT 26.7 修复的可固定上游 Collection，并重新验证稳定身份、nonat 读取及模式边界；或者用户单独明确授权供应商修复范围。按 design 第 1 节，公共依赖不兼容时暂停切换，不自行维护 fork。

任务 1.2 尚未完整通过，1.3 及后续实施暂停；不将前三类 NAT 单独交付冒充四资源目标完成。开发与 OCI 保留 26.1.11，DNAT placeholder 保留。未发布、部署、接触设备或修改 infra-ops。软件交付尚未完成，任务勾选以此边界为准。

安装方式补充：直接将 GitHub 源码 archive URL 交给 ansible-galaxy 会因缺少 MANIFEST.json 失败。后续兼容门槛通过后应使用固定 git SHA 的 Collection 源安装，或在构建阶段生成标准 Collection 包；不能把源码 archive 当成已经构建的 Galaxy 包。此次试装只使用临时目录，没有改动开发 Collection。
