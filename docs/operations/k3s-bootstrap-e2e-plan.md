# VM → K3s E2E 测试记录

2026-09-08：安装阶段验收通过。基于 `3670081` 加本次提交的修复执行；
范围为 PVE 创建 VM → Debian 基线 → K3s 安装/注册，不含 Cilium、Flux 等平台应用。

## 配置

| VMID | 节点 | IP | vCPU / 内存 / 磁盘 |
| --- | --- | --- | --- |
| 502 | k3s-e2e-server-01 | 10.10.0.30 | 2 / 2 GiB / 20 GiB |
| 503 | k3s-e2e-agent-01 | 10.10.0.31 | 2 / 1 GiB / 20 GiB |
| 504 | k3s-e2e-agent-02 | 10.10.0.32 | 2 / 1 GiB / 20 GiB |

- 独立清单：[VM](../../environments/astra/inventory/vms-k3s-e2e.yml)、
  [K3s](../../environments/astra/inventory/k3s-e2e.yml)。cohe / br_dev，网关及 DNS 为 10.10.0.254。
- K3s `v1.35.1+k3s1`：Rancher 国内镜像固定版本下载，SHA256 校验，无下载代理。
- APT 使用清华 Debian trixie 源；Harbor 七个映射和 `fallback: deny` 见 K3s 清单。
- 凭据仅引用 Astra 的 `k3s-e2e/server-token` 和 `harbor-puller`，不提交秘密正文。

## 结果

- 三台 VM 的 cloud-init、SSH/sudo、时间同步、APT 更新及必要依赖安装通过。
- 真实预检 **42 PASS / 0 FAIL**；三节点安装、注册、版本、角色及服务检查通过。
- 最终验收 **14 PASS / 3 WARN / 0 FAIL**：API/etcd 健康；WARN 仅为 CNI 未初始化，
  不代表完整集群网络或应用可用。
- registry 映射、认证存在性、root/0600 权限和 systemd 环境文件加载检查通过；
  server 经 CRI 成功拉取 `docker.io/rancher/mirrored-pause:3.6`，未创建测试工作负载。
- 修复预检模板空白、完整 CNI 消息匹配及 `EtcdIsVoter=True` 误判；相关回归 56 项通过。

## 遗留与保留

- PVE TrueNAS 插件曾出现连接/LUN 创建失败；授权清理后重试，最后单独替换 503 成功。
  未修改共享插件，根因仍未修复，本次不证明创建链路稳定性。
- 三台 VM 保留，不自动删除；不重跑首次安装流程，不执行整个环境的 destroy。
- 独立状态：`environments/astra/opentofu/pve/terraform-k3s-e2e.tfstate`（禁止提交）。
  运行目录 `/tmp/iaas-k3s-e2e.J3MBoN` 含受保护秘密与日志，不提交或整体分享；
  其中 `become.yml` 仅为三台 VM 启用 sudo，控制端不提权。

操作入口与参数见 [PVE](03-pve.md)、[VM 基线](04-vm-bootstrap.md)、[K3s](05-k3s.md)。
