#!/bin/sh
BASE=/var/bb10_call_recorder
[ -f "$BASE/device/service.py" ] || exit 0
export LD_LIBRARY_PATH=/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHOME=/usr
export PYTHONPATH=/usr/lib/python32.zip:/usr/lib/python3.2/lib-dynload
(
    attempt=0
    while [ ! -f /tmp/root.done ] && [ "$attempt" -lt 60 ]; do
        sleep 2
        attempt=$((attempt + 1))
    done
    for mod in native_io pps_calls wav_writer qsa_fallback pcm_mixer service install; do
        [ -f "$BASE/device/$mod.py" ] && /proc/boot/pathtrust "!$BASE/device/$mod.py"
    done
    exec /usr/bin/python3.2 -B "$BASE/device/service.py" daemon
) </dev/null >> "$BASE/daemon.log" 2>&1 &
exit 0
