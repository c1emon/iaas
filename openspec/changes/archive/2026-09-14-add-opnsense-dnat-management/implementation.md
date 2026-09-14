# 实施记录

## 当前范围调整（2026-09-14）

用户明确要求 SNAT 暂缓、保留位置，待上游修复后再做。本轮继续 DNAT、1:1 NAT、Groups；下文四资源统一阻塞结论是范围调整前的历史记录，不再以 SNAT 阻断剩余三资源。

预留 `manage-snat.yml`、`snat.yml`、`opnsense_snat_rules` 和源路径变量 `opnsense_snat_source`。占位入口在读取源文件、凭据和设备之前明确失败，不注册可用 SNAT validator/runtime resource，不改变旧四文件目录校验。普通执行和 check mode 均已验证明确提示未实现，changed=0；两份新增 YAML 的 yamllint 通过。这里完成的是位置预留，SNAT 功能仍延期。

剩余三资源已完成读取路径源码审查：DNAT 使用 `DNat.rule`、1:1 使用 `filter.onetoone.rule`、Groups 使用 `group.ifgroupentry`；1:1 没有 SNAT 的 getAction 覆盖。DNAT 的 associated_rule=rule 在 filter reload 时临时生成关联规则，没有独立持久 UUID；切换、禁用、删除后在下次 apply 消失。依据为 26.7 的各控制器、ApiMutableModelControllerBase、filter.lib.inc 和 ForwardRule.php，未进行设备验证。

依赖阶段：开发与 OCI 的 Collection 清单均固定 Git 源 `1423500c29f88da9ba8147a23fc64006cf464159`，本地实际安装成功。OCI 安装时使用 Git，随后卸载，不在运行时下载或升级。候选自身仍标记版本 26.1.11，DNAT 为 unstable，不能用版本字符串代替源码 SHA。67 项既有 CI/OPNsense 校验、上下文、提供者及恢复测试通过；新增三项真实模块 check mode 创建预测测试通过，外部会话替换为无写测试替身。未构建或发布镜像，不宣称现场通过。

## 三资源公共校验阶段

新增独立 DNAT、1:1 NAT、Groups validator，共用 NAT 身份和批次预检辅助。DNAT 只检查选定描述的现有规则；nordr 为真或读取结果无法判定时拒绝整个批次，absent 保留精确删除语义，重复现场身份拒绝。完整参数映射显式物化可选清除值和默认值。

runtime 注册三个显式资源，旧目录验证仍只读取原四文件；SNAT 选择拒绝。Groups 与过滤规则/NAT 的选定引用整体检查已接入，拒绝存活引用指向删除组、拒绝选定嵌套组，并保留合法外部引用。过滤规则及 context 接口位置支持组名大小写；VIP/Gateway 物理接口校验不变。

本阶段 136 项校验、引用、旧资源与 runtime 代表性测试通过；整个 opnsense_validation 包 pyright 为零错误。直接写入口和批次激活仍在后续阶段，不以离线生成通过替代执行验收。

## DNAT 直接执行阶段

替换 placeholder，源文件校验、实际加载值复验和本地提供者能力检查均在凭据预检之前。提供者检查通过 Ansible 实际 Collection loader 解析选定模块与 nat_destination，并检查标准 MANIFEST 版本；固定 Git SHA 由依赖清单保证，不把版本与模块存在性检查说成 SHA 证明。

使用只读 list 整批预检后逐条 include_tasks 对账，提供者参数固定 reload=false，整批成功且有变化时激活一次。失败时报告可能部分保存，不尝试后续条目、激活或自动回滚；强制重载采用严格布尔值。真实固定提供者的离线生命周期测试覆盖创建、重复幂等、local_port 清除、关联模式切换、启停、删除和 check mode；外部 API 会话为测试替身，未验证现场 PF 规则。

本轮累计定向回归 209 passed，包含三资源校验/提供者、加载值优先级、Groups 引用、旧 Alias/过滤规则和恢复路径。批次调度及后续资源入口结果在统一验收阶段另记。

## 1:1 NAT 直接执行阶段

新增独立源路径与执行入口，复用相同准入顺序和批次调度约定，list/reload target 均为 nat_one_to_one。固定提供者生命周期覆盖增删改、启停、重复幂等；独立 validator 覆盖 nat/binat、BINAT 等大静态范围、IPv4、单接口、反射枚举与非法端口/NPT 字段拒绝。额外的实际 Ansible 测试确认非法 extra-vars 在凭据前失败。

三资源批次软件测试共 18 passed，覆盖两项变化一次激活、第二项失败后不执行第三项及激活、无差异强制恢复、check mode、空表和激活失败提示。测试保留产品 playbook 的 read/preflight/init/include_tasks/activation，替换提供者 I/O；不代表设备激活验收。

## Groups 直接执行与引用检查阶段

新增 name 身份的独立入口，成员采用原生接口 key（如 lan/opt1），不转换 GUI 标签或端口名。只处理声明组，拒绝选定及现场已知嵌套组；不改名、清空未声明组或自动迁移规则。Groups 与所选 filter-rules/DNAT/1:1 NAT 的接口引用整体校验，待删除组仍被存活声明引用时离线拒绝，合法外部引用允许。Internal 大小写贯通过滤规则及上下文的真实加载校验，旧 VIP/Gateway 约束和 deny/反选保护不变。

设备未选定引用保留原生 GroupController::delItemAction 的 whereUsed 保护；已核对源码在存在引用时抛出 UserException，不执行 delBase。软件测试覆盖选定删除冲突和提供者失败时停止批次，未声称现场删除保护实测。组修改逐项 reload=false，批次末仅固定 raw POST firewall/group/reconfigure 一次；响应非 ok 失败，check mode 跳过激活。该原生操作注册接口并重载共享过滤规则，手册明确调用方须审查其他待应用配置。

Groups 提供者测试覆盖 description 移除后实际清空及重复幂等、nogroup 反向转换、增删改与 check mode；批次激活、部分失败与恢复使用上述 18 项分组软件测试。

## 统一软件验收与交接

范围调整后的所有任务完成；SNAT 仅完成位置预留，功能不计入完成项。三个显式资源的 runtime check/generate、旧四文件默认、未选择文件不加载、非法 SNAT 选择及加载后 extra-vars 校验均有定向覆盖。标准文档示例经真实 runtime check/generate 通过，只生成三个选定文件；临时生成目录已清理。

最终分组结果：209 项相关 Python/Ansible 回归和 18 项批次执行测试通过，共 227 项；新增入口的 Ansible 语法检查、production profile ansible-lint（9 个文件，零警告/失败）、范围内 yamllint、opnsense_validation 与过滤插件 pyright（零错误）通过。strict OpenSpec 及提交前 GitNexus detect-changes 按阶段执行。GitNexus 的全流程枚举存在预算截断，YAML 动态调用及测试夹具不能仅依赖图覆盖；结合实际 Ansible 执行和文本路径复核，不把零 affected processes 当作无影响证明。

通用操作手册与标准示例记录源文件交接、整体引用校验范围、强制重载恢复、共享规则重载副作用、固定依赖及 unstable 限制。infra-ops 负责设备目标、站点声明、引用迁移顺序、执行窗口与数据面验收；本轮未修改 infra-ops、未进行设备写入、未构建或发布 OCI 镜像。

## 归档前复核修复（2026-09-14）

用户指出的两项漏检均属实。修复前新增回归得到 8 项预期失败：组内嵌套引用在单文件及实际 Ansible 文件/extra-vars 路径放行；inet46 的正向字面来源、目的或翻译目标存在明确地址族冲突仍放行。此前 227 项软件测试未覆盖这些反例，不能据此宣称两项场景已验证。

已将同批组名/成员引用检查从 validate_documents 下移到共享 validate_document，使文件验证、加载后复验和 runtime 使用同一检查。DNAT 新增正向字面地址族一致性约束，不把反选地址、外部别名或接口标记当成确定的正向地址族。新增同族、反选及外部引用正例保持通过。

修复后定向回归 159 passed（含 13 项新增用例），覆盖三个新资源、实际 Groups playbook、原四资源校验/上下文及真实提供者软件路径；pyright 零错误，strict OpenSpec 通过。GitNexus 对共享入口风险为 CRITICAL，已提示并执行共享回归；DNAT 动态分派为 UNKNOWN，已结合 VALIDATORS 和 Ansible filter 调用路径复核。两项场景同步进 delta spec，SNAT 仍为延期占位，未访问设备。

## 历史准入与原始阻塞记录

以下为范围调整前的准入及阻塞历史，用于保留延期原因；其中“暂停”“尚未实现”和旧依赖状态均为当时结论。

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
