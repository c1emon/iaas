# 固定交付与验证结论

本文件保留当前可用产物及关键版本历史。验收范围、材料定位与保留规则统一见 [PVE 生命周期验收材料](../../../docs/operations/pve-lifecycle-acceptance.md)；任务状态见 [tasks](tasks.md)。IaaS 交付软件能力，不执行调用方的设施操作。

## 当前固定版本 rc.25

[v0.1.0-rc.25](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.25)，源码 `6cec8adf1b96c880561f96bb9d89a7caa7ba626a`；[发布工作流 36985693769](https://github.com/c1emon/iaas/actions/runs/36985693769) 7 个 jobs 全部成功。

```text
ghcr.io/c1emon/iaas-runtime@sha256:5857d1f2ede24e2dab4c2c5c3679c63e8d45bbff20f74398e5a6ad4f35fc2bfe
```

| 产物 | 实际摘要 |
| --- | --- |
| runtime manifest | `sha256:5857d1f2ede24e2dab4c2c5c3679c63e8d45bbff20f74398e5a6ad4f35fc2bfe` |
| linux/amd64 | `sha256:8ac86ae2ecd18e81ad652bb6529915dc09f42c30ec10fd16536983c97bf1bb79` |
| linux/arm64 | `sha256:bed6ec468b96f9e5e3db4dbd0e4e089b6ec948db07ef945a53c2ccd1ef4e10c4` |
| iaas-linux-amd64 SHA256 | `a2f0c8972d67757f0ccf25688f235ae6977b8e80787d792ee3824386af6d56b6` |
| iaas-darwin-arm64 SHA256 | `6939b71afa6e3ed2e1e5b049405a98b692eb2e3386e698ab3443134559f061ff` |

两个平台各 2132 passed、4 skipped；launcher 转移后的保存计划准入在实际待发布镜像中各 1 passed（断网），匿名固定 digest 拉取和 capabilities 调用通过。两个 launcher 已下载核 SHA256SUMS，macOS `--version` 返回 `iaas v0.1.0-rc.25`。

最近修正的本地验证为 147 项定向 Python、Ruff、Pyright 0 errors、4/4 import contracts、Go launcher 全套及 OpenSpec strict；覆盖未入池创建后删除、已有 VM 更新、真实池权限不足拒绝、软件 plan/apply/verify 删除路径和原材料字节保留。不同阶段测试集合不相加为覆盖数量。

当前合同：publication request v2、preview/result/record v3；acceptance request/result v3、preview v1；shared one-shot admission v2；recovery request/preview/result v1；snippet cleanup request/result v2。rc.19 acceptance v2 仅作为恢复原证据读取，不接受新 start 回退。

节点需按当前操作说明安装匹配的受限 upload/delete helper 和 wrapper-only sudo，冻结 SSH key/known_hosts。普通 VM pool 可选，provider 的空字符串/null均表示未入池；验收临时 VM pool 必填。当前活动无法核清阻断清理，历史 guest-exec 缺关联可由新限定批准处置；原结果不改写。

## 关键版本历史

| 版本 / 源码 | 关键变化或失败 | 发布与验证 |
| --- | --- | --- |
| rc.19 | 原 run-120-1 guest exec 权限403与遗留未知；保留原验收证据，不因后续清理改为成功 | 前置代理/截止交付见归档 change；不作为当前执行配置 |
| [rc.20](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.20) / `904e92e` | pool/VMID、当前模板与恢复合同首次集中交付；不含之后的审核修正 | [36862950966](https://github.com/c1emon/iaas/actions/runs/36862950966) 成功；每平台2093 passed、4 skipped |
| [rc.21](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.21) / `92b85aa` | 当前UPID/PID/helper活动未知必须阻断；普通VM完整必要权限预检恢复 | [36890195933](https://github.com/c1emon/iaas/actions/runs/36890195933) 成功；每平台2105 passed、4 skipped |
| [rc.22](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.22) / `0093093` | pending/reservation冒号引用原值保留；原journal精确绑定不变 | [36950707343](https://github.com/c1emon/iaas/actions/runs/36950707343) 成功；每平台2112 passed、4 skipped |
| [rc.23](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.23) / `829c092` | review.json传输、discovery与存储诊断修正；新增镜像测试漏传UID:GID | [36968614808](https://github.com/c1emon/iaas/actions/runs/36968614808) 失败，未形成可用的新镜像交付 |
| [rc.24](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.24) / `5d7fefc` | 镜像测试与正式launcher使用相同UID:GID；不降低protected_file校验 | [36980219960](https://github.com/c1emon/iaas/actions/runs/36980219960) 成功；每平台2124 passed、4 skipped，实际镜像准入通过 |
| rc.25 / `6cec8ad` | 普通VM provider空pool语义统一，真实池权限、保存计划/批准和验收必填pool不放宽 | 当前固定交付，详见上节 |

历史完整 manifest/platform/launcher 摘要保留在对应 Release 的 SHA256SUMS、CI及本文件 Git 历史中，不重复展开多份校验表。rc.20–22、24的匿名消费核验均已完成；旧版本的成功不授权当前重放旧计划。

## 结论限制

上述 CI、Go/Python fixtures、helper本地测试与镜像准入均为软件/产物验证，不是当前现场资源观察。rc.24之前的本地全套曾有一条macOS进程组 PermissionError，单独重跑通过；不能将其表述为该轮全套无失败。

调用方已记录限定恢复、9005验收及普通VM/专属snippet收尾。IaaS仅引用该范围结论，不把关机普通VM生命周期扩大为guest/业务验收，也不据此认定日常root接管、生产资格或完全无人工恢复的正常路径通过。原始执行材料仍由受保护存储保留。
