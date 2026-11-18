# BB10 通话录音 (`bb10-call-recorder`)

[English README](README.en.md) · [技术架构说明](docs/ARCHITECTURE.md) · [姊妹项目：BB10 VoLTE 官网](https://bb10-volte.octoooo.com/) · [OctoLab](https://octoooo.com/)

专为已获取 Root 权限的 **BlackBerry 10**（OS `10.3.3.3216`，支持 Q10 / Classic Q20 / Passport / P'9983 等全系列机型）打造的**原生离线通话录音应用与守护服务**。

由 **OctoLab** 独立制作并源码公开：零联网权限、开机自动值守、原生 Cascades 界面直接播放，也可在系统「文件管理器」或电脑 USB 中直接打开标准 WAV 录音文件。

---

## 核心特性

- **100% 纯本地离线，零联网权限**：手机端 `bar-descriptor.xml` **不申请 `access_internet` 权限**（由 CI 自动强制校验），从系统沙箱层面杜绝任何网络上传可能。
- **BB10 原生直播标准格式**：录音保存为 `16,000 Hz / 16-bit PCM` 标准 `.wav` 文件（自动设置 `1000:1001` 共享媒体权限），在 App 内或黑莓自带「文件管理器 → 语音 (`voice`)」中点开即播，无需转码。
- **自动录音 + 通话中手动启停**：
  - 精确订阅 `/pps/services/phone/private/calls` 状态机，仅在真正接通（`connected` / `multiparty`）时开始录音，振铃与拨号等待阶段不空录，挂断立即落盘。
  - **严格排除紧急呼叫**（`emergency` 状态永不触发录音），默认对文件名与列表中的电话号码脱敏（如 `138****0000`，可在设置中自选保留完整号码）。
- **双音源自适应架构**：
  1. **通用 QSA 增强采集（默认即用，兼容 VoLTE 与传统 2G/3G CS 通话）**：以硬件原生 `48 kHz / 双声道` 打开 `/dev/snd/pcmPreferredc`，经一阶去直流高通滤波、3:1 抗混叠抽取为 `16 kHz` 单声道并施加 `+18 dB` 软限幅增益，免提或听筒均可清晰拾音，中途切换蓝牙/免提自动重连声卡。
  2. **BB10 VoLTE 纯数字双向缓冲协同（可选）**：当手机安装了支持音频协同的新版 `bb10-volte` 时，可在设置中开启「VoLTE 纯数字内录协同」，直接对齐上行 TX 与下行 RX 数字 PCM 帧合成双声道立体声。
- **断电与低空间保护**：录音期间每 2 秒增量更新 RIFF/WAVE 头并执行 QNX6 `fsync` 快照提交；机身剩余空间低于 `200 MB` 时自动安全收尾，绝不撑满系统分区。

---

## 下载与三种安装方式

您可以根据习惯任选一种方式安装（均无需命令行）：

| 文件 | 适用场景 | 下载链接（国内高速 R2 镜像） |
| --- | --- | --- |
| `bb10-call-recorder-0.1.0.1.bar` | **方式一（最简单）**：使用 Sachesi / Darcy BBTools / Chrome 插件直接装入手机 | [下载 `.bar`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1.bar) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1.bar.sha256) |
| `bb10-call-recorder-0.1.0-r1-windows-x64.exe` | **方式二（已配对电脑一键装）**：自动复用本机 `BB10 VoLTE` 配对记录，一键装好桌面图标 + 后台服务 | [下载 Windows 助手 `.exe`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0-r1-windows-x64.exe) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0-r1-windows-x64.exe.sha256) |
| `bb10-call-recorder-0.1.0.1-bootstrap.zip` | **方式三（AutoRoot 扩展包）**：供熟悉 AutoRoot 安装器的进阶用户导入 | [下载 `bootstrap.zip`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1-bootstrap.zip) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1-bootstrap.zip.sha256) |

> 全部发行文件与总校验表亦可在 [GitHub Releases (`v0.1.0-r1`)](https://github.com/Octo-o-o-o/bb10-call-recorder/releases/tag/v0.1.0-r1) 获取。

### 方式一：手机侧载 `.bar`（无需电脑 SSH 配对）
1. 确保您的黑莓 BB10 手机已完成 Root（例如已使用过 [BB10 VoLTE](https://bb10-volte.octoooo.com/) 或 AutoRoot，系统中存在 `/bin/__root`）。
2. 用 Sachesi、Darcy's BBTools 或 Chrome BB10 插件安装 `bb10-call-recorder-0.1.0.1.bar`。
3. 在黑莓桌面打开 **「BB10 通话录音」**，点击 **「安装并启动录音后台」** 并确认合规提示，即告完成！此后重启手机也会随 AutoRoot 自动在后台启动。

### 方式二：Windows 桌面安装助手一键安装
1. 若您的电脑曾使用过 `BB10 VoLTE` 连接这台手机，用 USB 连接手机并打开 `bb10-call-recorder-0.1.0-r1-windows-x64.exe`。
2. 点击 **「一键安装手机 App 与开启自动录音」**，约 20 秒即可同时把「BB10 通话录音」图标装上手机桌面并启动后台服务。

---

## 录音文件在哪里？如何导出？

- **内置存储默认路径**：
  - 手机「文件管理器」：`设备 (Device) / voice / bb10-call-recorder/`
  - QNX 完整路径：`/accounts/1000/shared/voice/bb10-call-recorder/`
- **外置 SD 卡路径**（在 App「设置」中切换存储位置后）：
  - `/accounts/1000/removable/sdcard/voice/bb10-call-recorder/`
- **播放与复制**：
  - 在手机端可直接在「BB10 通话录音 → 录音列表」内播放/删除，或在系统「文件管理器」中点击 `.wav` 播放。
  - 连接电脑开启 USB 存储或 Wi-Fi 共享后，打开 `voice/bb10-call-recorder` 文件夹即可直接把 `.wav` 拷入电脑归档。

---

## 从源码构建与验证

```bash
# 运行全部单元测试与公开仓库隐私/零联网权限校验
python -m unittest discover -s tests -v
python tools/check_release.py

# 使用固定 SHA-256 的 BB10 NDK 容器离线编译原生 ARMv7 .bar
python tools/build_mobile.py

# 在 Windows (Python 3.14.9 + PyInstaller 6.22.3) 构建独立单文件桌面助手
python tools/build_windows.py
```

---

## 合规提示与开源许可

- **知情同意提醒**：部分国家或地区法律要求通话录音前须取得通话方知情同意。请在使用本工具前确认并遵守您所在地的法律法规。
- **开源许可证**：本项目采用 **[PolyForm Noncommercial License 1.0.0](LICENSE)** 开源。
  - **个人、爱好者、教学与非商业社区使用完全免费**，欢迎检阅源码、自行构建与提交改进。
  - **任何商业用途**（包括有偿代装服务、商业翻新机预装销售、付费分发等）须事先联系 **OctoLab**（`octoooo@octoooo.com`）获取独立的商业授权协议。

---

## OctoLab 与支持作者

> *“让老黑莓，再多用一阵。”*

如果您喜欢这个小工具，欢迎：
- 在 GitHub 为 **[Octo-o-o-o/bb10-call-recorder](https://github.com/Octo-o-o-o/bb10-call-recorder)** 点亮一颗 **Star**；
- 了解姊妹项目 **[BB10 VoLTE（中国移动 / 联通 / 电信 4G 高清语音与短信恢复）](https://bb10-volte.octoooo.com/)** 与 **[OctoLab 工作室](https://octoooo.com/)**；
- 在手机端 App 右上角点击 **「OctoLab」**（或桌面助手右上角点击 **「OctoLab · 支持与打赏」**），自愿请作者喝杯咖啡（支持支付宝 / 微信自选金额；打赏纯属心意，不构成商业授权）。
