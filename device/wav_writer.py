"""Streaming RIFF/WAVE file writer with periodic header checkpoints (Python 3.2+)."""
import os
import struct
import time

import native_io as nio


class StreamingWavWriter(object):
    def __init__(self, filepath, sample_rate=16000, channels=2, min_free_bytes=nio.MIN_FREE_BYTES):
        if sample_rate not in (8000, 16000, 32000, 44100, 48000):
            raise ValueError('Unsupported sample rate: %r' % (sample_rate,))
        if channels not in (1, 2):
            raise ValueError('Unsupported channel count: %r' % (channels,))
        if os.path.islink(filepath):
            raise RuntimeError('Refusing symlink output path')
        self.filepath = filepath
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.sample_width = 2
        self.min_free_bytes = int(min_free_bytes)
        self.data_bytes = 0
        self.stopped_low_disk = False
        self._fd = None
        self._last_sync = 0.0
        self._open()

    def _header_bytes(self, pcm_bytes):
        byte_rate = self.sample_rate * self.channels * self.sample_width
        block_align = self.channels * self.sample_width
        riff_size = 36 + int(pcm_bytes)
        return struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            riff_size & 0xffffffff,
            b'WAVE',
            b'fmt ',
            16,
            1,  # PCM
            self.channels,
            self.sample_rate,
            byte_rate,
            block_align,
            16,
            b'data',
            int(pcm_bytes) & 0xffffffff,
        )

    def _open(self):
        if nio.free_space_bytes(self.filepath) < self.min_free_bytes:
            raise RuntimeError('insufficient_disk_space')
        parent = os.path.dirname(self.filepath)
        if parent:
            nio.ensure_dir(parent, mode=0o775, shared_media=True)
        self._fd = os.open(self.filepath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o664)
        nio.make_shared_readable(self.filepath, mode=0o664)
        os.write(self._fd, self._header_bytes(0))
        self._last_sync = time.time()

    def write_pcm(self, raw_bytes):
        if self._fd is None or not raw_bytes:
            return False
        now = time.time()
        if now - self._last_sync >= 2.0:
            if nio.free_space_bytes(self.filepath) < self.min_free_bytes:
                self.stopped_low_disk = True
                return False
        frame_align = self.channels * self.sample_width
        usable = len(raw_bytes) - (len(raw_bytes) % frame_align)
        if usable <= 0:
            return True
        os.lseek(self._fd, 44 + self.data_bytes, os.SEEK_SET)
        view = raw_bytes[:usable]
        written = 0
        while written < usable:
            n = os.write(self._fd, view[written:])
            if n <= 0:
                raise RuntimeError('short_wav_write')
            written += n
        self.data_bytes += usable
        if now - self._last_sync >= 2.0:
            self.checkpoint()
            self._last_sync = now
        return True

    def checkpoint(self):
        if self._fd is None:
            return
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.write(self._fd, self._header_bytes(self.data_bytes))
        os.lseek(self._fd, 44 + self.data_bytes, os.SEEK_SET)
        os.fsync(self._fd)

    def duration_seconds(self):
        denom = float(self.sample_rate * self.channels * self.sample_width)
        return round(self.data_bytes / denom, 3) if denom else 0.0

    def close(self, remove_if_empty=True):
        if self._fd is None:
            return
        try:
            self.checkpoint()
        finally:
            fd = self._fd
            self._fd = None
            os.close(fd)
        if remove_if_empty and self.data_bytes == 0 and os.path.isfile(self.filepath):
            try:
                os.unlink(self.filepath)
            except OSError:
                pass
