# rc.26 交付

2026-10-03，[PR #39](https://github.com/c1emon/iaas/pull/39) 合并到 main，提交 `72e92035aaf40c32f67883ece3ce94b99670b9f5`；[v0.1.0-rc.26](https://github.com/c1emon/iaas/releases/tag/v0.1.0-rc.26) 固定到该提交。[发布工作流 37087831078](https://github.com/c1emon/iaas/actions/runs/37087831078) 7 个 jobs 全部成功。

| 产物 | 固定引用 |
| --- | --- |
| runtime（linux/amd64、linux/arm64） | `ghcr.io/c1emon/iaas-runtime@sha256:7f00394e577122897988bd65f8ec09752f630eb1aaf5af5db9ac8231f6e7a267` |
| image-builder（linux/amd64） | `ghcr.io/c1emon/iaas-image-builder@sha256:d3537b949738974464959a63ef0076839d810e5d235a862fc56c27aea76b6ed9` |
| version tag | 两个镜像均为 `v0.1.0-rc.26`；runtime 同时提供 `-amd64`、`-arm64` 平台 tag |
| launcher | Release 的 `iaas-linux-amd64`、`iaas-darwin-arm64` 与 `SHA256SUMS` |

两个 runtime 平台各2145 passed、4 skipped；Pyright 0 errors/0 warnings；实际待发布镜像中的 launcher 保存计划准入各1 passed。双平台 runtime 及 amd64 image-builder 匿名固定 digest 拉取、断网 capabilities 调用全部通过。registry manifest 已独立读取核对平台和上述 digest；两份 launcher 下载核 SHA256SUMS 通过，macOS `--version` 返回 `iaas v0.1.0-rc.26`。

check 根据 publish（默认）、cleanup、retire 选择输入及已有校验器，只读取所选 action 材料，保持离线、无 state/设施写入。accept/recover 分派与 plan/apply 删除准入不变，不需要升级请求合同。

调用方应固定新 runtime digest 后重跑相应离线 check，再按既有 plan/apply 准入执行模板退役与收尾。本交付不修改 infra-ops，不操作模板9006或其他设施，不将软件验证表述为现场最终验收成功。已按用户确认删除本地和远程实现分支。
