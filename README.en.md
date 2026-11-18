# BB10 Call Recorder (`bb10-call-recorder`)

[中文说明](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Sister Project: BB10 VoLTE](https://bb10-volte.octoooo.com/en/) · [OctoLab](https://octoooo.com/)

A **100% offline, native call recording app and background daemon** for rooted **BlackBerry 10** phones (`OS 10.3.3.3216` — Q10, Classic Q20, Passport, P'9983, and all hardware variants).

Built by **OctoLab** with full source code available: zero internet permissions, automatic boot startup via AutoRoot, built-in native Cascades audio playback, and standard `.wav` files directly accessible in BB10 File Manager or over USB.

---

## Highlights

- **Strict Zero-Internet Sandbox**: `mobile/native/bar-descriptor.xml` requests **no `access_internet` permission** (enforced automatically by CI), guaranteeing recordings never leave your phone over the network.
- **Native BB10 Playback (`16 kHz` PCM WAV)**: Recordings are streamed as standard `16,000 Hz / 16-bit` RIFF/WAVE files with shared media permissions (`1000:1001`, `0664`), so they play out of the box in both the **BB10 Call Recorder** app and BlackBerry's built-in **File Manager → Voice**.
- **Automatic & Mid-Call Manual Recording**:
  - Tracks `/pps/services/phone/private/calls` and records only during active speech (`connected` / `multiparty`) — never during dialing or ringing.
  - **Strictly excludes emergency calls** (`emergency` call state/type is never recorded) and masks phone numbers by default (`+86****00`, configurable in Settings).
- **Dual Audio Capture Path**:
  1. **Enhanced QSA Capture (Default — works for both VoLTE & legacy 2G/3G CS calls)**: Opens `/dev/snd/pcmPreferredc` at native `48,000 Hz / 2ch`, applies a DC-blocking high-pass filter, 3:1 decimates to `16,000 Hz` mono with `+18 dB` soft-limiting gain, and seamlessly re-attaches on speakerphone/Bluetooth route switches.
  2. **BB10 VoLTE Digital Dual-Channel Buffer (Optional)**: Pairs with newer `bb10-volte` builds supporting `/var/bb10_volte/audio-tap.json` to align pure digital uplink TX + downlink RX PCM streams into stereo WAVs.
- **Crash-Safe Checkpointing & Disk Guard**: Flushes RIFF/WAVE headers with QNX6 `fsync` every 2 seconds and stops cleanly if free storage drops below `200 MB`.

---

## Downloads & 3 Easy Setup Options

Choose whichever workflow fits your setup — no command line required:

| Package | Best For | Direct Download (R2 CDN) |
| --- | --- | --- |
| `bb10-call-recorder-0.1.0.1.bar` | **Option 1 (Easiest)**: Sideload with Sachesi / Darcy BBTools / Chrome Extension, then tap Activate in the app | [Download `.bar`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1.bar) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1.bar.sha256) |
| `bb10-call-recorder-0.1.0-r1-windows-x64.exe` | **Option 2 (One-Click Windows Helper)**: Reuses your existing `BB10 VoLTE` PC pairing to install the app + enable auto-record in one click | [Download Windows `.exe`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0-r1-windows-x64.exe) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0-r1-windows-x64.exe.sha256) |
| `bb10-call-recorder-0.1.0.1-bootstrap.zip` | **Option 3 (AutoRoot Bootstrap)**: Addon archive for AutoRoot package installer users | [Download `bootstrap.zip`](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1-bootstrap.zip) · [SHA-256](https://bb10-downloads.octoooo.com/call-recorder/v0.1.0-r1/bb10-call-recorder-0.1.0.1-bootstrap.zip.sha256) |

> All release artifacts and `SHA256SUMS.txt` are also published on [GitHub Releases (`v0.1.0-r1`)](https://github.com/Octo-o-o-o/bb10-call-recorder/releases/tag/v0.1.0-r1).

---

## Accessing & Exporting Recordings

- **Internal Shared Voice Folder (Default)**:
  - BB10 File Manager: `Device / voice / bb10-call-recorder/`
  - Full QNX Path: `/accounts/1000/shared/voice/bb10-call-recorder/`
- **Removable SD Card** (selectable in App Settings):
  - `/accounts/1000/removable/sdcard/voice/bb10-call-recorder/`

---

## Building from Source

```bash
# Run unit tests & privacy / zero-internet verification
python -m unittest discover -s tests -v
python tools/check_release.py

# Build the native ARMv7 Cascades .bar in the pinned offline BB10 NDK container
python tools/build_mobile.py

# Build the standalone Windows x64 helper (Python 3.14.9 + PyInstaller 6.22.3)
python tools/build_windows.py
```

---

## Legal Notice & License

- **Call Recording Consent**: Many jurisdictions require one-party or all-party consent before recording a telephone conversation. You are solely responsible for complying with applicable laws in your jurisdiction.
- **License**: Licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.
  - **Free for personal, hobbyist, academic, and noncommercial use.**
  - **Commercial use** (including paid installation services or bundling on commercially sold refurbished phones) requires a separate paid commercial license from **OctoLab** (`octoooo@octoooo.com`).

---

## OctoLab & Supporting the Maker

If this project keeps your BlackBerry useful a little longer:
- Give **[Octo-o-o-o/bb10-call-recorder](https://github.com/Octo-o-o-o/bb10-call-recorder)** a **Star** on GitHub;
- Check out our sister project **[BB10 VoLTE](https://bb10-volte.octoooo.com/en/)** and **[OctoLab](https://octoooo.com/)**, or tap **OctoLab** in the top-right corner of the app to buy the maker a coffee (Alipay / WeChat optional tip).
