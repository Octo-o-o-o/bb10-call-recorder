# Contributing to `bb10-call-recorder`

Thank you for helping improve BlackBerry 10 software preservation!

## Ground Rules

1. **Zero Private Data in Commits**:
   - Never include device PINs, IMEIs, IMSIs, phone numbers, SSH keys (`q10_root_rsa`, `id_rsa`, `known_hosts`), personal call recordings, or machine-specific paths in code, tests, commit messages, or pull requests.
   - Always run `python tools/check_release.py` before committing.

2. **Strict Offline Guarantee**:
   - `mobile/native/bar-descriptor.xml` must never add `<permission>access_internet</permission>`.

3. **QNX Python 3.2 Compatibility for `device/` and `mobile/runtime/`**:
   - On-device scripts run on BB10 OS `10.3.3.3216`'s built-in `/usr/bin/python3.2`.
   - Avoid Python 3.3+ syntax (`f-strings`, `pathlib`, `subprocess.run`, `time.monotonic`, or `with wave.open(...)`).
   - Remember `/usr/bin/python3.2 -c` is disabled when `euid == 0`; always execute verified file paths registered via `/proc/boot/pathtrust`.

4. **Pre-Submit Checklist**:
   ```bash
   python -m unittest discover -s tests -v
   python tools/gui.py --self-test
   python tools/check_release.py
   ```

## Licensing

By contributing to this repository, you agree that your contributions may be distributed under the repository's `PolyForm-Noncommercial-1.0.0` license as well as OctoLab's commercial licensing terms.
