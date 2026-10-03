# Debian 13 通用模板代表性配置

当前 build request/v2、publish request/v2、record/preview/result/v3；不接受旧构建版本。
示例地址、摘要、VMID 和身份由调用方替换，不是执行批准。

- 构建：复用 [build request](../image-publish/image-build-request.json)，8 GiB、清华 Debian/security 源、
  `package_upgrade: true`、七项基础工具、cloud-init/growpart、QGA。构建内存预算独立于模板 1 GiB。
- 发布：`publish-request.json` 表达 9000、2 核、1024 MiB、8 GiB、`bridge: null`，无 `ip_config`。
  `local` 用于暂存上传镜像，`memory` 用于系统盘和 cloud-init 盘；暂存存储须允许 import 内容及上传/删除。
  artifact、摘要和对象引用必须替换为此次成功构建材料，现有 artifact 是合成数据。
- 日常克隆：`environment.yml` 选择 `cluster.yml` / `vms.yml`，完整克隆，8 核、8192 MiB、
  128 GiB、memory、dev；启动前设置 br_dev、10.10.0.100/24、10.10.0.254、10.5.0.15。
  示例 VMID 1000 仅为占位，实际 VMID、MAC、身份和启动策略由 infra-ops 正式清单决定。

正例：明确容量与布尔升级、null 网卡发布、零网卡来源完整克隆到 128 GiB。
反例：缺失容量、布尔容量、字符串升级、9 GiB 基础盘缩到 8 GiB、null 网卡同时指定
ip_config、未知字段、linked clone、克隆盘小于来源盘。由
`tests/python/test_debian13_general_template.py` 覆盖，均不读取凭据。

离线 check 通过只表示合同可接受；基础盘实际容量在下载后核验。
真实验收使用新的只读准入及一次性 admission，在既有 iaas-acceptance 池的 500–550
空闲 VMID 完整克隆，独立配置网络/身份并验证自动扩容、cloud-init/QGA、源模板不变。
最后只清理本次临时 VM、盘和 snippet，保留模板 9000。
专用验收池的结果与 dev 池的日常部署及业务验收分别表述。

infra-ops 负责正式清单、权限/凭据接线、计划审批、日常 apply 开放和部署后验收。
