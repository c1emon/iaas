## 1. 实施准入与统一依赖

- [x] 1.1 明确开始实施后重新核对分支/工作树和两仓边界，刷新 GitNexus 并分析共享校验/分派影响；以真实分支状态与影响记录为准，本轮文档授权不能替代实施授权。（见 implementation.md）
- [ ] 1.2 解析候选 Collection 完整 SHA，检查相对 26.1.11 的差异和四模块依赖；用固定源码/API 模型及最小兼容测试核对 SNAT target_port/no_nat、DNAT disabled/关联过滤、1:1 类型/反射/范围和 Groups 成员标识/reconfigure/引用保护；确认只读列举能按稳定身份判断已有 nonat/nordr 模式。公共依赖或所需语义不兼容时报告阻塞，不自行维护 fork。
- [ ] 1.3 兼容检查通过后固定开发及 OCI 的同一依赖源，验证四模块可加载、check mode 和当前四类资源代表性回归；记录 unstable 与软件证据范围，形成独立依赖提交，不发布镜像。

## 2. 统一约定与可选资源接入

- [ ] 2.1 建立三类 NAT 公共身份和生命周期辅助，四个资源独立 validator/分派，不建立万能 NAT 字段模型；以各类最小合法/非法输入、资源间同名身份合法及类内冲突拒绝、未知字段与严格类型测试为依据。SNAT/DNAT 对 present 精确匹配对象增加写前只读模式核对，代表性测试 nonat/nordr 为真或无法判定时整批首写前拒绝、正常规则可更新及 absent 仍可精确删除，不转换例外模式。
- [ ] 2.2 接入四个显式 resource/file key 和 runtime 离线 check/generate 选择，不新增 launcher apply；按 design 的四个直接 Ansible 入口与源路径变量接收生成文件，指定 inventory/limit，复用同一合同验证源文件和实际加载值，再做凭据预检。验证旧四文件目录不要求新增文件、未选择资源不被自动纳管、空表不清空对象，以有/无新增资源场景、生成文件交接和 extra-vars 非法值测试为依据，独立提交。

## 3. Source NAT（独立阶段）

- [ ] 3.1 实现 SNAT 声明/校验和精确增量 playbook；测试字面端口/范围、整数 target_port、static_port 冲突、no_nat 明确拒绝、地址族和外部引用；确认不切换出站 NAT 模式、不操作自动规则，形成 SNAT 阶段提交。

## 4. Destination NAT（独立阶段）

- [ ] 4.1 替换 DNAT placeholder，接入独立参数和增删改/启停；测试 nat_reflection、associated_rule、大小写/disabled 转换、关联模式切换及删除、local_port 字面范围拒绝、no_port_forward 拒绝、重复身份处理，形成 DNAT 阶段提交，不添加站点 WAN-only 校验。

## 5. One-to-one NAT（独立阶段）

- [ ] 5.1 实现 1:1 NAT 声明与增量入口；测试 nat/binat 区分、显式 BINAT 范围等大、反射枚举、单接口、禁用/删除和非法端口/NPTv6 字段拒绝，形成 1:1 NAT 阶段提交。

## 6. Firewall Groups（独立阶段）

- [ ] 6.1 实现 name 身份、成员和独立 group 入口；测试固定 API 接受的成员标识、gui_group 反向字段、组序号、空/重复成员/嵌套组拒绝，确保未声明系统/VPN 组保持，形成 Groups 阶段提交。
- [ ] 6.2 接入选定声明引用校验与原生删除保护；为现有 filter-rules.interface/context.interface_networks 作最小组名兼容，验证 Internal 声明→过滤引用→上下文→实际加载校验保持大小写，VIP/Gateway 物理接口及既有 deny/反选保护不放宽。验证被引用组删除拒绝、合法外部引用不强制闭合、改名不隐式重写规则、组 reconfigure 真实目标与共享重载副作用记录，不级联删除或推导 ACL。

## 7. 统一验收与交付

- [ ] 7.1 针对四类资源分组验证重复对账、absent、check mode 无写/无激活、逐项 reload=false、单资源成功一次激活、部分失败停止和强制重载恢复；确认省略可选字段映射为有效清除/默认值，以 SNAT target_port 移除后启用 static_port、DNAT local_port 清除和 Groups description 移除后的重复幂等覆盖，不以 omit 保留旧值。共同逻辑复用测试，原生分歧用代表性例覆盖，不声称跨资源事务。
- [ ] 7.2 完成固定 Collection 集成、runtime 场景及原有四类回归、相关 lint、strict OpenSpec 和 GitNexus 变更分析；记录软件/现场区别，未知结果不得以其他资源通过替代。
- [ ] 7.3 更新三类 NAT、Groups 通用手册、标准文件示例和 infra-ops 交接说明；核对字段与入口一致、声明与全局模式边界、依赖限制和恢复步骤，提交软件交付记录，不写本站参数/迁移批次，不自动发布或部署。
