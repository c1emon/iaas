# 新模板最小克隆验收与 VM 专属 snippet 清理

## Why

现有模板发布返回配置核验结果，不能证明完整克隆可以启动、guest-agent 可用或本次 cloud-init 注入已生效。现有 snippet manifest 和受限 helper 支持生成、上传及摘要核验，但 VM 删除后没有受控清理入口。调用方需要这两项独立的技术结果，决定是否推广模板及关闭清理待办。

## What Changes

- 新增一次性模板验收：固定模板及发布记录 → 完整克隆 → 启动 → 固定只读 guest-agent 检查 → 清理 → 分项及总体结果。
- 新增删除 VM 后的精确 snippet 清理；复核原生成/上传记录、VM 缺席、内容摘要和完整引用范围，允许仅对原清单单独补执行。
- 复用 launcher、当前模板记录、执行准入、私有任务记录、PVE HTTPS、snippet manifest、SSH 主机校验和受限 helper；不重新建设普通 VM plan/apply 或镜像发布。
- 发布版本化 request/result、launcher 能力声明、双方共用正反例，以及必要的 helper 安装和最小权限说明。

## Capabilities

### New Capabilities

- `pve-template-acceptance`: 一次完整克隆的最小技术验收及临时资源收尾。
- `pve-snippet-cleanup`: 已删除 VM 的精确、可补执行 snippet 清理。

### Modified Capabilities

- `runtime-launcher`: 新入口的输入发现、凭据隔离、文件传输、能力版本和结果收集。

## Impact

预计涉及 `src/iaas/pve_template/`、`src/iaas/pve_inventory/cloud_init_helpers/`、`src/iaas/runtime_execution/`、`automation/launcher/`、`automation/pve-node/`、节点 bootstrap，以及相应 schema、文档和定向测试。实现量级 M（2–5 天），按合同、执行、清理、launcher/测试分段；以 A/B 必要正确性及定向安全检查为范围。

本 change 以当前代码及 `separate-image-build-and-pve-publish` 的已实现合同为基础；规划时未将该 change 的现场重复发布验收纳入本 change 的隐含范围；随后用户单独授权的现场测试已提供其完成证据，两项任务分别记录。现有普通 VM 的 guest/business 外部验收语义不变。

## Non-goals and delivery boundary

不做性能压测、多次重启、硬件矩阵、业务部署、guest SSH 或外网连通测试。不修改 infra-ops available 台账，不实现 n8n、邮件、审批、Forgejo 编排或 Runner checkout 自动 prepare-dependencies。不新增签名链、通用编排框架、逐磁盘内容 hash 或资格系统。

软件完成条件是合同、可调用入口、定向正反例、相关校验和版本说明；真实 PVE 验证需另行限定节点、VMID、存储及授权窗口。本提案不构成现场操作授权。
