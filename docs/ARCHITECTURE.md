# BB10 通话录音架构设计说明

## 1. 为什么采用「独立软件 + VoLTE 可选数字音频缓冲」双层架构

1. **职责与隐私隔离**：`BB10 VoLTE` 是面向全机型三网注册、短信修复与系统恢复的底层通信基础设施，不应混入日常高频录音回放、文件管理界面或额外音频采集权限。将 `BB10 通话录音`（`com.octolab.bb10recorder`）独立为单独的 Cascades 应用，且在 `bar-descriptor.xml` 中**不申请 `access_internet` 网络权限**，从系统沙箱层面保证录音 100% 留在本机。
2. **突破 BB10 沙箱下耳机/听筒录音瓶颈**：
   - 传统 BB10 录音软件只能访问物理麦克风 `/dev/snd/pcmPreferredc`，听筒模式下对端音量极低（约 `-47 dBFS`），插入有线耳机或连接蓝牙耳机后对端声音完全消失。
   - 对 OS `10.3.3.3216` 的 `ims_rrm`（`ImsAudioImpl`）反汇编确认，VoLTE 通话的上下行线性 PCM 均经过 `libasound.so.2` 的 4 个固定 PLT 调用点（`0x7f7d8`、`0x7fa92`、`0x7fdac`、`0x8078a`）。
   - 在 `bb10-volte` 中提供默认关闭的可选被动环形缓冲（`audio-tap.json` 显式授权后生效）：`ims_rrm` 内部零系统调用、零锁、零文件句柄，仅将 20 ms `S16_LE` 音频帧写入自有 `.bss` 循环缓冲区，通话线程无阻塞风险。
3. **全场景兜底**：当处于 2G/3G 电路域（CS）通话或尚未启用 VoLTE 数字缓冲时，守护进程自动回退至 QSA `/dev/snd/pcmPreferredc`（`16 kHz` 单声道 + 一阶直流阻断高通滤波 + `+18 dB` 软限幅增益），确保未装 VoLTE 的已 Root 设备同样可用。

## 2. 通话状态机（基于 `/pps/services/phone/private/calls`）

| PPS `callstate` | 录音动作 | 说明 |
| --- | --- | --- |
| `incoming` / `connecting` / `remote_ringing` | 不启动 | 振铃与拨号等待阶段绝不提前建文件 |
| `connected` / `multiparty` | 启动并持续写入 | 真正接通后才创建 WAV 流 |
| `held` | 保持当前会话 | 通话保持期间不切断当前录音文件 |
| `disconnected` / `failed` / 对象移除 | 刷盘封尾并写入索引 | 更新 RIFF/WAVE 长度头并 `fsync` |
| 任一呼叫 `calltype == emergency` | 强制跳过 / 立即停录 | 110/112/119/120/911 等紧急呼叫零干预 |

## 3. 存储与断电安全保护

- 严禁向 `/tmp`（QNX 内存盘）写入正式录音文件；所有音频直接流式写入 `/accounts/1000/shared/voice/bb10-call-recorder` 或外置 SD 卡。
- 每 2 秒原地刷新一次 44 字节 RIFF/WAVE 头部长度并执行 `fsync`，即使通话中意外断电或重启，已录制部分仍是标准可播放的 `.wav` 文件。
- 每次检查点均校验目标分区可用空间，低于 `200 MB` 安全阈值时自动平稳收尾停录。
