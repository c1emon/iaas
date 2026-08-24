# Astra Homelab 架构清单

> 本文基于已恢复的历史架构记录和当前 OPNsense 只读导出结果重建。实际配置以当前设备导出为准；旧规划中与当前事实不一致的部分已在“待确认”处标注。

## 1. 全局约定

### VLAN / 网段

原规划中多数 VLAN 网段遵循：

```text
10.{VLAN_ID}.0.0/24
```

当前已确认 LAN 实际使用 `192.168.99.0/24`，不是旧规划中的 `10.99.0.0/24`。

| VLAN | 名称 | 原规划网段 | 当前确认 | 用途 |
|---:|---|---|---|---|
| 1 | Management | `10.1.0.0/24` | 是 | 管理面、管理面板、IPMI/BMC、交换机管理 |
| 10 | Dev Net | `10.10.0.0/24` | 待确认 | 开发网络 |
| 21 | ISP / ONU | `10.21.0.0/24` | 待确认 | PPPoE 承载、ONU 管理访问 |
| 33 | Storage Net | `10.33.0.0/24` | 待确认 | PVE ↔ TrueNAS 存储网络 |
| 50 | App Net | `10.50.0.0/24` | 是，DNS 转发目标中出现 | 生产应用、基础服务、数据库、对象存储 |
| 99 | LAN | 原规划 `10.99.0.0/24` | 当前 `192.168.99.0/24` | 普通上网、调试、测试、配置 |

---

## 2. 物理设备清单

| 设备 | 角色 | 说明 |
|---|---|---|
| OPNsense 物理机 | 核心路由 / 防火墙 | 单 10G Trunk 接入核心交换机 Port 3 |
| 核心交换机 | 核心二层汇聚 | 12 口 10G 光口弱三层管理交换机，不承担三层路由 |
| 接入交换机 | ONU / AP / LAN 接入 | 4 口 10G SFP+，1 口千兆电口，支持 PoE 输入 |
| 汇聚交换机 | 下级汇聚 | 8 口千兆 + 2 口 10G |
| 管理交换机 | 管理网汇聚 | 48 口千兆非管理交换机，纯二层 |
| PVE node3 | 虚拟化节点 | Proxmox 集群节点 |
| PVE cohe | 虚拟化节点 | Proxmox 集群节点 |
| TrueNAS SCALE | 集中存储 / 数据服务 | HDD 池、SSD 池、数据库、Redis、MinIO |
| N100 | 基础服务节点 | Docker 运行 Authentik、Harbor、Postfix、SmartDNS、Traefik |
| RK3588 ARM | 代理节点 | Debian，运行 sing-box |

---

## 3. OPNsense

| 项目 | 配置 |
|---|---|
| 主机名 | `soter` |
| FQDN | `soter.mgmt.clemon.cis` |
| 管理 / API 地址 | `https://10.1.0.254` |
| 角色 | 核心路由 / 防火墙 |
| 使用网口 | 1 个 10G 网口 |
| 连接位置 | 核心交换机 Port 3 |
| 端口模式 | Trunk |
| 承载 VLAN | 1 / 10 / 21 / 33 / 50 / 99 |
| ISP VLAN | VLAN 21 |
| 上网方式 | PPPoE |
| DDNS | ddns-go |
| Nginx | OPNsense 本机运行 |
| 公网入口端口 | TCP `883` |
| Nginx 监听端口 | 本机 `883` |
| Nginx 模式 | TCP stream SNI passthrough |

### 公网入口链路

```text
Internet
  │
  │ TCP 883
  ▼
OPNsense WAN
  │
  │ Port Forward: 883 → local 883
  ▼
OPNsense 本机 Nginx
  │
  │ TCP stream / SNI passthrough
  ▼
Traefik-Dev / Traefik-Infra / Traefik-App
```

### 当前 Ansible 管理边界

当前已接入：

- API 只读检查
- 配置 snapshot
- 本地只读导出
- 手写、受审查的 firewall aliases、IP Alias VIP、PBR gateway 与新的 API-backed filter rules

当前暂不接管：

- ISC DHCP
- DHCPv6 / Prefix Delegation
- Interfaces / VLANs
- legacy firewall rules 与管理访问规则
- NAT
- WAN / PPPoE

---

## 4. DNS / 域名

### DDNS

| 项目 | 配置 |
|---|---|
| DDNS 工具 | ddns-go |
| 部署位置 | OPNsense |
| DNS 托管 | Cloudflare |
| 动态解析域名 | `sh.dc.clemon.icu` |

### DNS 链路

```text
普通 DNS 请求
客户端
  → OPNsense Unbound
  → AdGuard Home
  → 外部上游 DNS

clemon.icu / clemon.cis 后缀域名
客户端
  → OPNsense Unbound
  → SmartDNS / 10.50.0.15

App Net DNS
App Net 客户端
  → SmartDNS / 10.50.0.15
```

### 当前已导出的 Unbound Host Overrides

| FQDN | IP | 说明 |
|---|---:|---|
| `core.sw.mgmt.clemon.cis` | `10.1.0.20` | Core Switcher |
| `access.sw.mgmt.clemon.cis` | `10.1.0.21` | Access Switcher |
| `subcore.sw.mgmt.clemon.cis` | `10.1.0.22` | Subcore Switcher |
| `memory.mgmt.clemon.cis` | `10.1.0.210` | TrueNAS |
| `dockge.memory.mgmt.clemon.cis` | `10.1.0.210` | `memory` 的 alias |
| `soter.mgmt.clemon.cis` | `10.1.0.254` | OPNsense |
| `proxy.host.clemon.cis` | `10.40.0.253` | Sing Box Bare Metal，和旧规划 IP 不一致 |
| `ups.mgmt.clemon.cis` | `10.1.0.10` | UPS |
| `bootstrap.host.clemon.cis` | `10.1.0.15` | N100 / bootstrap host |

### 当前已导出的 Unbound Forwarding

| Domain | Target | Port | Forward first | 说明 |
|---|---:|---:|---|---|
| 空 / 默认 | `127.0.0.1` | `1053` | false | AdGuard Home |
| `clemon.icu` | `10.50.0.15` | `53` | true | SmartDNS |
| `clemon.cis` | `10.50.0.15` | `53` | true | SmartDNS |
| `scut.edu.cn` | `114.114.114.114` | `53` | false | 外部解析 |

---

## 5. 当前 Firewall Aliases

| Name | Type | Content | Description |
|---|---|---|---|
| `proxy_gw` | host | `10.40.0.253` | 代理网关，和旧规划 RK3588 地址不一致 |
| `fakeip` | network | `198.18.0.0/15`, `fc00::/18` | FakeIP 网段 |
| `tailnet` | network | `100.65.0.0/16`, `fd7a:115c:a1e0::a/48` | TailScale |

---

## 6. DHCP / IPv6 现状

### DHCPv4

当前仍使用 ISC DHCP，Kea DHCP 当前禁用且无 subnet / reservation。

已确认：

- 无 ISC static mappings。
- DHCP range 约定为 `x.x.x.100` 到 `x.x.x.220`。
- 当前租约显示 LAN 与 MGMT 有动态客户端。

当前观测：

| Interface | 说明 | 观测 |
|---|---|---|
| `lan` / LAN | 普通 LAN | `192.168.99.0/24` 动态租约，约 20+ 个客户端 |
| `opt1` / MGMT | 管理网 | 有 `10.1.0.x` 动态租约 |

### DHCPv6 / Prefix Delegation

当前存在 DHCPv6 IA_NA 和 IA_PD 租约。

观测到：

- LAN 上存在多个 IA_NA 动态地址租约，例如 `240e:388:c200:5200::/64` 段内地址。
- 存在 IA_PD prefix lease：`240e:388:c200:52f0::/62`。

因此 DHCP 后端迁移需要单独设计，短期不建议从 ISC 迁移到 Kea。

---

## 7. 核心交换机

| 项目 | 配置 |
|---|---|
| 管理 IP | `10.1.0.20` |
| 类型 | 12 口 10G 光口弱三层管理交换机 |
| 三层路由 | 不参与 |
| VLAN 间路由 | 全部由 OPNsense 负责 |

### 核心交换机端口表

| 端口 | VLAN / 模式 | 连接设备 | 用途 |
|---:|---|---|---|
| 1 | Access VLAN 1 | 备用 | 管理网备用 |
| 2 | VLAN 1 / 21 / 99 | 接入交换机 | ONU / LAN / 管理 |
| 3 | Trunk VLAN 1 / 10 / 21 / 33 / 50 / 99 | OPNsense | 核心路由 |
| 4 | VLAN 1 / 10 / 21 / 50 / 99 | 汇聚交换机 | 下级汇聚 |
| 5 | VLAN 10 / 50 | node3 业务口 | Dev / App |
| 6 | VLAN 10 / 50 | cohe 业务口 | Dev / App |
| 7 | VLAN 10 / 50 | 备用 | PVE 扩展 |
| 8 | Access VLAN 50 | TrueNAS App 口 | 应用网络 |
| 9 | Access VLAN 33 | node3 存储口 | 存储网络 |
| 10 | Access VLAN 33 | cohe 存储口 | 存储网络 |
| 11 | Access VLAN 33 | 备用 | 存储扩展 |
| 12 | Access VLAN 33 | TrueNAS 存储口 | 存储网络 |

---

## 8. 接入交换机

| 项目 | 配置 |
|---|---|
| 管理 IP | `10.1.0.21` |
| 规格 | 4 口 10G SFP+，1 口千兆电口 |
| 千兆电口 | 支持 PoE 输入 |
| 上联 | 核心交换机 Port 2 |
| 上联模式 | Trunk |
| 承载 VLAN | 1 / 21 / 99 |

TODO：补充接入交换机具体端口划分。

---

## 9. 汇聚交换机

| 项目 | 配置 |
|---|---|
| 管理 IP | `10.1.0.22` |
| 规格 | 8 口千兆 + 2 口 10G |
| 上联 | 核心交换机 Port 4 |
| 上联模式 | Trunk |
| 承载 VLAN | 1 / 10 / 21 / 50 / 99 |
| 三层路由 | 不参与，仅二层转发 |

### 下联设备

| 设备 | 说明 |
|---|---|
| N100 | 基础服务节点 |
| RK3588 | sing-box 代理节点 |
| 管理交换机 | 汇聚所有主机管理网口 |

---

## 10. 管理交换机

| 项目 | 配置 |
|---|---|
| 类型 | 非管理交换机 |
| 管理 IP | 无 |
| 规格 | 48 口千兆 |
| 上联 | 汇聚交换机 |
| 上联模式 | Access VLAN 1 |
| 用途 | 汇聚所有设备管理网口 / IPMI / BMC |

TODO：补充具体管理口接入清单和 IPMI / BMC 地址表。

---

## 11. TrueNAS SCALE

| 项目 | 配置 |
|---|---|
| 系统 | TrueNAS SCALE |
| 管理 IP | `10.1.0.210` |
| 存储 IP | `10.33.0.210` |
| 应用 IP | `10.50.0.210` |
| 管理口 | 独立千兆电口，VLAN 1 |
| 25G 口 1 | VLAN 33，存储网络 |
| 25G 口 2 | VLAN 50，应用网络 |

### 存储池

| 池名称 | 类型 | 用途 |
|---|---|---|
| `bitocean` | 12 × 14T HDD / RAIDZ2 | 图片、视频、文档等普通数据 |
| `lightning` | SSD / RAIDZ1 / 约 3.3T | 数据库、虚拟机磁盘、高性能数据 |

### PVE 存储

| 项目 | 配置 |
|---|---|
| 存储方式 | ZFS over iSCSI |
| 使用池 | `lightning` |
| 网络 | VLAN 33 |
| TrueNAS IP | `10.33.0.210` |
| 实现项目 | `boomshankerx/proxmox-truenas` |

### TrueNAS 应用

| 服务 | 说明 |
|---|---|
| 数据库实例 | 数据位于 `lightning` |
| Redis 实例 | 运行在 TrueNAS SCALE |
| MinIO 实例 | 提供 S3 兼容对象存储 |
| JuiceFS | 用于 POSIX 兼容挂载 |

### 数据保护

| 项目 | 当前状态 |
|---|---|
| 快照 | 未配置 / 待确认 |
| 外部备份 | 未配置 / 待确认 |
| UPS | 已接入 |
| UPS 型号 | Eaton 5PX 1500i RT2U |
| 自动关机 | 未配置 / 待确认 |

---

## 12. PVE 集群

| 节点 | 域名 | 管理 IP |
|---|---|---|
| node3 | `node3.ops.clemon.icu` | `10.1.0.73` |
| cohe | `cohe.ops.clemon.icu` | `10.1.0.72` |

| 项目 | 配置 |
|---|---|
| 集群 | 已组成 Proxmox Cluster |
| HA | 不涉及硬件直通的 VM 启用 HA |
| 管理口 | 独立千兆电口，VLAN 1 |
| 业务口 | VLAN 10 / 50 共用 |
| 存储口 | VLAN 33 独享 |
| 共享存储 | TrueNAS `lightning` |
| 存储方式 | ZFS over iSCSI |

### 主要虚拟机服务

| 服务 | 说明 |
|---|---|
| Dockge | Docker Compose 管理面，存在多个实例 |
| MinIO | S3 兼容对象存储实例 |
| Nextcloud | 私有云 / 文件协作 |
| Collabora | 在线 Office 协作组件 |
| RustDesk | 远程桌面服务 |
| Reader3 | 阅读 / RSS 类服务 |
| Traefik | 反向代理实例 |
| Consul | 服务发现 / 配置相关组件 |
| qBittorrent | 下载服务 |
| Emby | 媒体服务 |
| Jellyseerr | 媒体请求管理 |
| ChineseSubFinder | 中文字幕自动下载 |
| Prowlarr | 索引器管理 |
| Sonarr | 剧集自动化管理 |
| Radarr | 电影自动化管理 |

TODO：补充各服务所在 VM / 节点、VLAN / IP / 域名、公网暴露状态。

---

## 13. N100 基础服务节点

| 项目 | 配置 |
|---|---|
| 管理 IP | `10.1.0.15` |
| 应用 IP | `10.50.0.15` |
| 接入位置 | 汇聚交换机 |
| 网口模式 | 单口 Trunk |
| 承载 VLAN | VLAN 1 / VLAN 50 |
| 运行方式 | Docker |

### Docker 服务

| 服务 | 作用 |
|---|---|
| Authentik | SSO / 统一认证 |
| Harbor | 镜像仓库 |
| Postfix | SMTP / 邮件服务 |
| SmartDNS | 内部 DNS / FakeIP 分流 |
| Traefik | Infra 基础服务反向代理 |

---

## 14. RK3588 ARM 节点

| 项目 | 原规划配置 |
|---|---|
| 管理 IP | `10.1.0.253` |
| Dev IP | `10.10.0.253` |
| App IP | `10.50.0.253` |
| 接入位置 | 汇聚交换机 |
| 网口模式 | 单口 Trunk |
| 系统 | Debian |
| 公网暴露 | 无 |

当前 OPNsense 导出中代理相关地址为 `10.40.0.253`，需确认是否已变更网络规划。

### sing-box

| 项目 | 配置 |
|---|---|
| 入口 | tproxy / HTTP / SOCKS5 |
| 出站 | VLESS 等协议 |
| 使用网络 | 原规划 VLAN 10、VLAN 50；当前待确认 |
| FakeIP | 由 N100 SmartDNS 实现 |
| 代理出口 | RK3588 sing-box |

---

## 15. 防火墙 / 访问策略

| 规则 | 说明 |
|---|---|
| 默认策略 | 各 VLAN 间默认不允许互访 |
| 可访问外网 VLAN | VLAN 10 / 50 / 99 |
| VLAN 99 / LAN | 可访问所有网络，用于配置、测试、调试；当前实际为 `192.168.99.0/24` |
| 管理网 | 主要允许 LAN / 调试网络访问 |
| VLAN 33 | 存储专用，主要用于 PVE ↔ TrueNAS |
| 数据库 / 对象存储 | 位于 VLAN 50，与 VLAN 33 无关 |

---

## 16. 当前 TODO

### Traefik

- [ ] Dev Traefik 部署位置
- [ ] App Traefik 部署位置
- [ ] Infra Traefik 详细路由
- [ ] SNI 分流规则
- [ ] 域名命名规则
- [ ] TLS 证书来源
- [ ] 公网暴露服务清单

### 服务清单

- [ ] 服务名
- [ ] 域名
- [ ] IP / 端口
- [ ] 部署位置
- [ ] 所属网络
- [ ] 是否公网暴露
- [ ] 是否接入 Authentik

### DNS / 域名

- [ ] Cloudflare DNS 记录清单
- [ ] SmartDNS 规则
- [ ] FakeIP 规则范围
- [ ] `clemon.icu` / `clemon.cis` 内部解析清单

### 监控 / 告警

- [ ] Uptime Kuma
- [ ] Grafana / Prometheus
- [ ] 日志系统
- [ ] TrueNAS 告警
- [ ] OPNsense 告警
- [ ] UPS 告警
- [ ] 证书过期提醒

### 备份 / 灾备

- [ ] TrueNAS 快照策略
- [ ] TrueNAS 外部备份
- [ ] PVE VM 备份
- [ ] 数据库备份
- [ ] 配置备份
- [ ] UPS 自动关机策略

### 交换机 / 管理口

- [ ] 接入交换机端口表
- [ ] 汇聚交换机端口表
- [ ] 管理交换机接入清单
- [ ] IPMI / BMC 地址表
