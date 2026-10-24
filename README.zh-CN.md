# UniXNU-umi — 小米 10

[English](README.md) | 简体中文

面向 **小米 10（`umi` / SM8250）** 的独立 UniXNU 移植。已在一台
**12 GiB 内存 / 256 GB 存储**的手机上进入 **iPadOS 17.7.11 Hello／设置向导**。
第 80 版已由机主确认 XNU 下 ST FTS 触摸可用，尚未验证完成设置和进入桌面。
本仓库发布开发源码，不提供可直接安装的发行镜像。

| 仓库 | 用途 |
| --- | --- |
| [UniXNU-umi](https://github.com/reAAAq/UniXNU-umi) | 板级配置、XNU 接入、驱动、诊断和主机工具 |
| [uefi-umi](https://github.com/reAAAq/uefi-umi) | 从 uefi-sheng 派生的 Mu-Silicium 固件移植 |
| [UniXNU](https://github.com/UniXNU/UniXNU) | 上游构建器、加载器、通用驱动和补丁 |

## 当前状态

截至 2026-10-23 的第 80 轮，以下结论仅针对已测试手机。

| 功能 | 状态与范围 |
| --- | --- |
| UEFI 菜单、RAM 负载、DarwinBoot | 已验证菜单、文件读取和内核交接 |
| 音量选择、电源确认、Restart | UEFI 中可用；不代表 iOS 实体键已适配 |
| XNU、多核、中断、定时器 | 已记录 8 核在线及各核 timer / IPI 活动 |
| UFS、OS、SystemOS | 已挂载并执行 launchd 和后续系统服务 |
| 可写 Data | 测试布局下已持久化并跨重启使用 |
| 显示 | 苹果 Logo 和 Hello／设置向导；CPU 复制到继承显存 |
| ST FTS 触摸 | XNU 下可用；第 80 版机主已确认真实触摸有效，UEFI 菜单触摸未验证 |
| GPU 加速 | 未实现 |
| Wi-Fi、蓝牙、蜂窝、音频、相机、传感器 | 未实现或未完成验证 |
| XNU USB、电池管理、休眠唤醒 | 未验证；Recovery ADB 不等于 XNU USB 可用 |

[验证摘要](docs/validation.json)记录去除设备标识后的关键数值和产物哈希。
原始设备转储和控制台日志保留在本地。前一版记录到 PM8150B GPIO5 输出低，
第 80 版按原生配置在 FTS 启动前启用这一路常开电源，之后机主确认触摸有效。
本轮坐标／HID 计数尚未采集；此前零事件日志保留为历史记录。

## 构建与目录

[BUILD.md](docs/BUILD.md)列出了固定版本、工作区组装、主机校验及尚需本地准备的输入。
`source-lock.json` 固定已验证框架与固件版本；`feeds.toml` 和 `unixnu.lock` 固定公开源码依赖。
`board.toml`／`umi_defconfig` 仍是最小源码基线，完整 Hello 配置由 `bringup/` 工具组装，
不能将默认通用构建视为完整系统镜像。

系统输入为 **iPad7,1 / 17.7.11 / 21H461 / j120ap**；源码内核为
**XNU 10063.141.1 / Darwin 23.6.0**，与 IPSW 内二进制内核版本不同。
Apple 组件、厂商固件、Data 种子和设备转储均不包含在仓库中。

- `scripts/`、`patches/`：ADT、构建及内核适配。
- `package/`：PMGR 服务、UFS/SMMU、Data、显示、诊断及 ST FTS/HID。
- `overlay/`、`menu/`：固件和菜单的生成输入；固件仓库保留已组装的继承显示、实体键和 RAM 负载配置。
- `bringup/tools/`、`bringup/tests/`：主机构建、日志解码、故障注入检查和 trust cache 打包。
- `docs/`：构建说明（含 [trust cache 打包](docs/BUILD.md)）、当前验证结果和构建限制。

完整系统构建仍依赖本地生成的 ABI、策略、镜像身份和硬件采集记录，尚不是干净克隆后的一键安装流程。

**Trust cache 打包**：payload 步骤所需的 trust cache bundle 在本仓库内生成
（`scripts/fetch-ipsw-members.py` + `bringup/tools/prepare_umi_trustcache.py`），
并由 `Build umi trust cache bundle` CI workflow 发布为 artifact。该 artifact 的下载链接
即为上游 `macos.yml` 的 `trust_cache_url` 参数值；IPSW 本身不会被完整下载，
仅通过 HTTP range 请求读取 `BuildManifest.plist` 与两个 `*.dmg.trustcache` 成员。
当前触控已接入 GPI DMA I²C、三次 GPIO 复位、只读模组身份读取及 HID 有效位／集合派发。
常开电源修复见 [138d6cb](https://github.com/reAAAq/UniXNU-umi/commit/138d6cb)，
源码对照和测试过程见[原生驱动审计](docs/TOUCH_NATIVE_AUDIT.md)。
多点触控、休眠唤醒和完成设置仍需单独验证；XNU 触摸可用不代表 UEFI 触摸可用。

分区范围与高位内存窗口只在当前容量配置上测量过，其他机型或容量必须重新核对。
测试安装替换了 Android userdata；本仓库不提供通用刷机脚本，请保留 Recovery 和备份。

## 致谢与许可

基于 UniXNU、UniXNU-sheng、Mu-Silicium，以及公开的 Xiaomi／LineageOS SM8250 资料。
原有逐文件许可和 `upstream.json` 来源信息均保留，见 [NOTICE.md](NOTICE.md) 与 [LICENSE](LICENSE)。
维护者为 [reAAAq](https://github.com/reAAAq)，本项目由社区独立维护。