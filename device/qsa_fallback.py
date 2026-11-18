"""QSA /dev/snd/pcmPreferredc audio input helper with DC-block & gain (Python 3.2+)."""
import array
import ctypes
import errno
import struct
import sys
import time


class QsaFormat(ctypes.Structure):
    _fields_ = [
        ('interleave', ctypes.c_uint32),
        ('format', ctypes.c_int32),
        ('rate', ctypes.c_int32),
        ('voices', ctypes.c_int32),
        ('special', ctypes.c_int32),
        ('reserved', ctypes.c_uint8 * 124),
    ]


class QsaBlock(ctypes.Structure):
    _fields_ = [
        ('frag_size', ctypes.c_int32),
        ('frags_min', ctypes.c_int32),
        ('frags_max', ctypes.c_int32),
        ('frags_buffered_max', ctypes.c_uint32),
        ('reserved', ctypes.c_uint8 * 120),
    ]


class QsaParams(ctypes.Structure):
    _fields_ = [
        ('channel', ctypes.c_int32),
        ('mode', ctypes.c_int32),
        ('sync', ctypes.c_uint64 * 2),
        ('format', QsaFormat),
        ('digital', ctypes.c_uint8 * 304),
        ('start_mode', ctypes.c_int32),
        ('stop_mode', ctypes.c_int32),
        ('time_flags', ctypes.c_int32),
        ('why_failed', ctypes.c_uint32),
        ('block', QsaBlock),
        ('subchannel', ctypes.c_char * 32),
        ('cross_core', ctypes.c_uint32),
        ('reserved', ctypes.c_uint8 * 92),
    ]


def apply_dc_block_and_gain(pcm_s16_le, gain_num=8, gain_den=1, state=None):
    """Apply first-order DC high-pass filter and soft-saturated gain (+18 dB default)."""
    if not pcm_s16_le:
        return b''
    usable = len(pcm_s16_le) - (len(pcm_s16_le) % 2)
    if usable <= 0:
        return b''
    samples = array.array('h')
    if hasattr(samples, 'frombytes'):
        samples.frombytes(pcm_s16_le[:usable])
    else:
        samples.fromstring(pcm_s16_le[:usable])
    if sys.byteorder != 'little':
        samples.byteswap()
    if state is None:
        state = {'prev_x': 0, 'prev_y': 0}
    prev_x = state.get('prev_x', 0)
    prev_y = state.get('prev_y', 0)
    for idx in range(len(samples)):
        x = int(samples[idx])
        # y[n] = x[n] - x[n-1] + 0.992 * y[n-1]
        y = x - prev_x + ((prev_y * 254) >> 8)
        prev_x = x
        prev_y = y
        boosted = (y * gain_num) // gain_den
        if boosted > 32767:
            boosted = 32767
        elif boosted < -32768:
            boosted = -32768
        samples[idx] = boosted
    state['prev_x'] = prev_x
    state['prev_y'] = prev_y
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tobytes() if hasattr(samples, 'tobytes') else samples.tostring()


def decimate_48k_stereo_to_16k_mono(pcm_48k_2ch):
    """Convert 48 kHz interleaved stereo S16_LE into 16 kHz mono S16_LE (3:1)."""
    if not pcm_48k_2ch:
        return b''
    # 1 output frame = 3 stereo frames = 12 bytes
    usable = len(pcm_48k_2ch) - (len(pcm_48k_2ch) % 12)
    if usable <= 0:
        return b''
    src = array.array('h')
    if hasattr(src, 'frombytes'):
        src.frombytes(pcm_48k_2ch[:usable])
    else:
        src.fromstring(pcm_48k_2ch[:usable])
    if sys.byteorder != 'little':
        src.byteswap()
    out_count = len(src) // 6
    dst = array.array('h', [0] * out_count)
    for i in range(out_count):
        base = i * 6
        # Average 3 left samples (identical to right on BB10 pcmPreferredc, or L+R/2)
        s0 = (int(src[base]) + int(src[base + 1])) >> 1
        s1 = (int(src[base + 2]) + int(src[base + 3])) >> 1
        s2 = (int(src[base + 4]) + int(src[base + 5])) >> 1
        dst[i] = (s0 + s1 + s2) // 3
    if sys.byteorder != 'little':
        dst.byteswap()
    return dst.tobytes() if hasattr(dst, 'tobytes') else dst.tostring()


class QsaMicCapture(object):
    def __init__(self, device_path=b'/dev/snd/pcmPreferredc', rate=48000, channels=2, output_16k_mono=True, lib=None):
        if ctypes.sizeof(QsaParams) != 752 or QsaParams.block.offset != 488:
            raise RuntimeError('unexpected_qsa_abi')
        self.device_path = device_path
        self.rate = int(rate)
        self.channels = int(channels)
        self.output_16k_mono = bool(output_16k_mono)
        self._lib = lib
        self._handle = ctypes.c_void_p()
        self._prepared = False
        self._fragment = 4096
        self._rem = b''
        self._dsp_state = {'prev_x': 0, 'prev_y': 0}

    def _bind_lib(self):
        if self._lib is None:
            self._lib = ctypes.CDLL('/lib/libasound.so.2', use_errno=True)
            specs = (
                ('snd_pcm_open_name', [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
                ('snd_pcm_plugin_params', [ctypes.c_void_p, ctypes.POINTER(QsaParams)], ctypes.c_int),
                ('snd_pcm_plugin_set_disable', [ctypes.c_void_p, ctypes.c_uint], ctypes.c_uint),
                ('snd_pcm_plugin_setup', [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_int),
                ('snd_pcm_plugin_prepare', [ctypes.c_void_p, ctypes.c_int], ctypes.c_int),
                ('snd_pcm_plugin_read', [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint], ctypes.c_int),
                ('snd_pcm_plugin_flush', [ctypes.c_void_p, ctypes.c_int], ctypes.c_int),
                ('snd_pcm_close', [ctypes.c_void_p], ctypes.c_int),
            )
            for name, argtypes, restype in specs:
                fn = getattr(self._lib, name)
                fn.argtypes = argtypes
                fn.restype = restype

    def start(self):
        self._bind_lib()
        rc = self._lib.snd_pcm_open_name(ctypes.byref(self._handle), self.device_path, 0x1002)
        if rc != 0 or not self._handle.value:
            raise RuntimeError('qsa_open_failed:%d' % rc)
        try:
            self._lib.snd_pcm_plugin_set_disable(self._handle, 2)
            params = QsaParams()
            params.channel, params.mode = 1, 1
            params.start_mode, params.stop_mode = 1, 1
            params.format.interleave, params.format.format = 1, 4
            params.format.rate, params.format.voices = self.rate, self.channels
            params.block.frag_size = 2048 if self.rate <= 16000 else 4096
            params.block.frags_min, params.block.frags_max = 1, -1
            rc = self._lib.snd_pcm_plugin_params(self._handle, ctypes.byref(params))
            if rc != 0:
                raise RuntimeError('qsa_params_failed:%d:%d' % (rc, int(params.why_failed)))
            setup = ctypes.create_string_buffer(2048)
            struct.pack_into('<i', setup, 0, 1)
            rc = self._lib.snd_pcm_plugin_setup(self._handle, setup)
            if rc != 0:
                raise RuntimeError('qsa_setup_failed:%d' % rc)
            frag = struct.unpack_from('<i', setup.raw, 456)[0]
            frame_bytes = 2 * self.channels
            if frag < frame_bytes or frag > 65536 or (frag % frame_bytes) != 0:
                raise RuntimeError('qsa_invalid_fragment:%d' % frag)
            self._fragment = frag
            rc = self._lib.snd_pcm_plugin_prepare(self._handle, 1)
            if rc != 0:
                raise RuntimeError('qsa_prepare_failed:%d' % rc)
            self._prepared = True
            self._buf = ctypes.create_string_buffer(self._fragment)
        except Exception:
            self.close()
            raise

    def read_chunk(self, apply_gain=True):
        if not self._handle.value or not self._prepared:
            return b''
        rc = self._lib.snd_pcm_plugin_read(self._handle, self._buf, self._fragment)
        if rc > 0:
            raw = self._buf.raw[:rc]
            if self.output_16k_mono and self.rate == 48000 and self.channels == 2:
                combined = self._rem + raw
                usable = len(combined) - (len(combined) % 12)
                self._rem = combined[usable:]
                raw = decimate_48k_stereo_to_16k_mono(combined[:usable])
            return apply_dc_block_and_gain(raw, state=self._dsp_state) if apply_gain else raw
        if rc == 0 or rc in (-errno.EAGAIN, -errno.EINTR):
            time.sleep(0.01)
            return b''
        raise RuntimeError('qsa_read_failed:%d' % rc)

    def close(self):
        try:
            if self._prepared and self._handle.value:
                self._lib.snd_pcm_plugin_flush(self._handle, 1)
        finally:
            self._prepared = False
            if self._handle.value:
                handle = self._handle
                self._handle = ctypes.c_void_p()
                self._lib.snd_pcm_close(handle)
