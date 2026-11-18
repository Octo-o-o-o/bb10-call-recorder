"""Stereo and mono PCM ring-buffer alignment and sample-rate conversion (Python 3.2+)."""
import array
import struct
import sys


RING_BYTES = 65536
RING_MASK = RING_BYTES - 1
SAFE_WINDOW = RING_BYTES - 4096


def _s16_array(raw):
    usable = len(raw) - (len(raw) % 2)
    arr = array.array('h')
    if usable <= 0:
        return arr
    if hasattr(arr, 'frombytes'):
        arr.frombytes(raw[:usable])
    else:
        arr.fromstring(raw[:usable])
    if sys.byteorder != 'little':
        arr.byteswap()
    return arr


def _array_bytes(arr):
    if sys.byteorder != 'little':
        out = array.array('h', arr)
        out.byteswap()
        return out.tobytes() if hasattr(out, 'tobytes') else out.tostring()
    return arr.tobytes() if hasattr(arr, 'tobytes') else arr.tostring()


def upsample_8k_to_16k(pcm_8k):
    """Linearly interpolate 8 kHz mono S16_LE samples to 16 kHz mono S16_LE."""
    src = _s16_array(pcm_8k)
    n = len(src)
    if n == 0:
        return b''
    dst = array.array('h', [0] * (n * 2))
    for i in range(n - 1):
        a = int(src[i])
        b = int(src[i + 1])
        dst[2 * i] = a
        dst[2 * i + 1] = (a + b) >> 1
    dst[2 * (n - 1)] = src[n - 1]
    dst[2 * (n - 1) + 1] = src[n - 1]
    return _array_bytes(dst)


def align_and_interleave(near_pcm, far_pcm, mode='stereo', max_silence_pad_samples=3200):
    """Combine near-end and far-end S16_LE mono streams with DTX silence padding.

    When one side pauses sending frames during DTX silence while the other side
    continues advancing, pad up to max_silence_pad_samples per poll cycle so the
    two channels remain time-aligned over long conversations.
    """
    near = _s16_array(near_pcm)
    far = _s16_array(far_pcm)
    n_len = len(near)
    f_len = len(far)
    if n_len == 0 and f_len == 0:
        return b'', b'', b''

    target = max(n_len, f_len)
    if n_len < target and (target - n_len) <= max_silence_pad_samples:
        near.extend([0] * (target - n_len))
        n_len = target
    if f_len < target and (target - f_len) <= max_silence_pad_samples:
        far.extend([0] * (target - f_len))
        f_len = target

    paired = min(n_len, f_len)
    rem_near = _array_bytes(near[paired:]) if n_len > paired else b''
    rem_far = _array_bytes(far[paired:]) if f_len > paired else b''
    if paired == 0:
        return b'', rem_near, rem_far

    if mode == 'mono':
        out = array.array('h', [0] * paired)
        for i in range(paired):
            mixed = (int(near[i]) + int(far[i]))
            if mixed > 32767:
                mixed = 32767
            elif mixed < -32768:
                mixed = -32768
            out[i] = mixed
        return _array_bytes(out), rem_near, rem_far

    out = array.array('h', [0] * (paired * 2))
    for i in range(paired):
        out[2 * i] = near[i]
        out[2 * i + 1] = far[i]
    return _array_bytes(out), rem_near, rem_far


class RingSliceCursor(object):
    """Tear-free circular audio buffer consumer using sequence counters."""

    def __init__(self):
        self.initialized = False
        self.last_total = 0
        self.session_count = 0

    def poll(self, read_fn, ring_offset):
        hdr1 = struct.unpack('<8I', read_fn(ring_offset, 32))
        seq_pre_1, total_1, rate, channels, fmt, session, chunks, seq_post_1 = hdr1
        if session == 0:
            return {'ready': False, 'pcm': b'', 'rate': 16000, 'channels': 1}
        if not self.initialized or session != self.session_count:
            self.initialized = True
            self.session_count = session
            self.last_total = total_1
            return {'ready': True, 'pcm': b'', 'rate': rate or 16000, 'channels': channels or 1}

        delta = (total_1 - self.last_total) & 0xffffffff
        if delta == 0:
            return {'ready': True, 'pcm': b'', 'rate': rate or 16000, 'channels': channels or 1}
        if delta > SAFE_WINDOW:
            self.last_total = (total_1 - (RING_BYTES // 2)) & 0xffffffff
            delta = RING_BYTES // 2

        start = self.last_total & RING_MASK
        pcm_base = ring_offset + 32
        first = min(delta, RING_BYTES - start)
        part1 = read_fn(pcm_base + start, first)
        part2 = read_fn(pcm_base, delta - first) if delta > first else b''

        hdr2 = struct.unpack('<8I', read_fn(ring_offset, 32))
        total_2 = hdr2[1]
        if ((total_2 - self.last_total) & 0xffffffff) > SAFE_WINDOW:
            self.last_total = total_2
            return {'ready': True, 'pcm': b'', 'rate': rate or 16000, 'channels': channels or 1}

        self.last_total = total_1
        return {
            'ready': True,
            'pcm': part1 + part2,
            'rate': rate or 16000,
            'channels': channels or 1,
        }
