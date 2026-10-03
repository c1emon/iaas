# 修复模板 check 的 action 分派

## Why

rc.25 的 `pve-template/check` 固定读取并校验发布请求，合法 cleanup/retire 输入会被拒绝，阻断模板退役前的离线检查。

## What Changes

- check 根据 publish（默认）、cleanup、retire 选择输入和已有校验器。
- 只加载所选 action 的输入，不读取无关输入、设施凭据或原执行目录。
- 未知 action 拒绝；摘要包含实际 action 和对应请求摘要。
- 保持离线、无 state 或设施写入；保留 accept/recover 现有专用分派。

## Impact

- 影响 `pve-template-lifecycle`，runtime 的 check 分支及输入选择。
- 不改变合同版本或 plan/apply 删除准入，不操作设施或 infra-ops。
