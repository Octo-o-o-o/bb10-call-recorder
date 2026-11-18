"""Unit and cross-module integration tests for BB10 Call Recorder."""
import ast
import ctypes
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'device') not in sys.path:
    sys.path.insert(0, str(ROOT / 'device'))

import native_io as nio
import pcm_mixer
import pps_calls
import qsa_fallback
import service
import wav_writer


class Python32CompatibilityTests(unittest.TestCase):
    def test_device_and_runtime_sources_avoid_py36_syntax(self):
        targets = list((ROOT / 'device').glob('*.py')) + [ROOT / 'mobile/runtime/entry.py']
        self.assertGreaterEqual(len(targets), 6)
        for path in targets:
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.JoinedStr, 'f-string forbidden in Python 3.2: ' + str(path))
                self.assertNotIsInstance(node, ast.AsyncFunctionDef, 'async forbidden in Python 3.2: ' + str(path))


class PpsCallsStateTests(unittest.TestCase):
    def test_ringing_never_starts_recording_until_connected(self):
        ringing_raw = (
            b'callstate::incoming\n'
            b'calltype::voice\n'
            b'callernumber::+12025550134\n'
            b'additional_info:json:{"connection_info":{"connection_type":"ir_92","connection_path":"ims_cellular"}}\n'
        )
        entry = pps_calls.parse_call_entry('call_1', ringing_raw)
        self.assertTrue(entry['is_volte_hint'])
        self.assertFalse(entry['is_emergency'])
        dec = pps_calls.evaluate_recording_decision([entry])
        self.assertFalse(dec['eligible'])
        self.assertEqual(dec['reason'], 'waiting_for_answer')

        entry['state'] = 'connected'
        dec2 = pps_calls.evaluate_recording_decision([entry])
        self.assertTrue(dec2['eligible'])
        self.assertEqual(dec2['reason'], 'connected')

    def test_emergency_calls_always_excluded(self):
        sos = pps_calls.parse_call_entry('sos', b'callstate::connected\ncalltype::emergency\ncallernumber::112\n')
        normal = pps_calls.parse_call_entry('c1', b'callstate::connected\ncalltype::voice\ncallernumber::10000\n')
        dec = pps_calls.evaluate_recording_decision([normal, sos])
        self.assertFalse(dec['eligible'])
        self.assertEqual(dec['reason'], 'emergency_call_excluded')

    def test_number_masking(self):
        self.assertEqual(pps_calls.mask_number('+1 202-555-0178', keep_number=False), '+12****78')
        self.assertEqual(pps_calls.mask_number('+1 202-555-0178', keep_number=True), '+12025550178')


class StreamingWavTests(unittest.TestCase):
    def test_streaming_wav_writes_valid_header_and_stops_on_low_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / 'sub/sample.wav')
            writer = wav_writer.StreamingWavWriter(out, sample_rate=16000, channels=2, min_free_bytes=1024)
            pcm = struct.pack('<4h', 1000, -1000, 2000, -2000) * 4000
            self.assertTrue(writer.write_pcm(pcm))
            writer.close()
            with wave.open(out, 'rb') as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 16000)
                self.assertEqual(wf.getnframes(), 8000)

            empty_out = str(Path(tmp) / 'empty.wav')
            empty_writer = wav_writer.StreamingWavWriter(empty_out, sample_rate=16000, channels=1, min_free_bytes=1024)
            empty_writer.close(remove_if_empty=True)
            self.assertFalse(Path(empty_out).exists())


class QsaAndMixerTests(unittest.TestCase):
    def test_qsa_abi_and_gain_saturation(self):
        self.assertEqual(ctypes.sizeof(qsa_fallback.QsaParams), 752)
        self.assertEqual(qsa_fallback.QsaParams.block.offset, 488)
        raw = struct.pack('<4h', 0, 1000, 10000, -10000)
        boosted = qsa_fallback.apply_dc_block_and_gain(raw, gain_num=8, gain_den=1)
        vals = struct.unpack('<4h', boosted)
        self.assertEqual(vals[2], 32767)
        self.assertEqual(vals[3], -32768)

        stereo_48k = struct.pack('<12h', 300, 300, 600, 600, 900, 900, -300, -300, -600, -600, -900, -900)
        mono_16k = qsa_fallback.decimate_48k_stereo_to_16k_mono(stereo_48k)
        self.assertEqual(struct.unpack('<2h', mono_16k), (600, -600))

    def test_upsample_interleave_and_ring_cursor(self):
        pcm_8k = struct.pack('<3h', 100, 300, 500)
        pcm_16k = pcm_mixer.upsample_8k_to_16k(pcm_8k)
        self.assertEqual(struct.unpack('<6h', pcm_16k), (100, 200, 300, 400, 500, 500))

        near = struct.pack('<4h', 10, 20, 30, 40)
        far = struct.pack('<2h', -10, -20)
        stereo, rem_n, rem_f = pcm_mixer.align_and_interleave(near, far, mode='stereo')
        self.assertEqual((rem_n, rem_f), (b'', b''))
        self.assertEqual(struct.unpack('<8h', stereo), (10, -10, 20, -20, 30, 0, 40, 0))

        # Verify RingSliceCursor over a wrap-around circular buffer
        ring_mem = bytearray(32 + 65536)
        struct.pack_into('<8I', ring_mem, 0, 1, 65000, 16000, 1, 4, 1, 100, 1)
        cursor = pcm_mixer.RingSliceCursor()
        first = cursor.poll(lambda off, n: bytes(ring_mem[off:off + n]), 0)
        self.assertEqual(first['pcm'], b'')

        payload = bytes((i & 0xff) for i in range(1200))
        for idx, b in enumerate(payload):
            ring_mem[32 + ((65000 + idx) & 0xffff)] = b
        struct.pack_into('<8I', ring_mem, 0, 2, 66200, 16000, 1, 4, 1, 102, 2)
        second = cursor.poll(lambda off, n: bytes(ring_mem[off:off + n]), 0)
        self.assertEqual(second['pcm'], payload)


class ServiceConfigAndIndexTests(unittest.TestCase):
    def test_config_volte_tap_and_recording_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = str(Path(tmp) / 'rec')
            volte = str(Path(tmp) / 'volte')
            Path(volte).mkdir()
            voice = str(Path(tmp) / 'voice')
            with mock.patch.object(service, 'INTERNAL_VOICE_DIR', voice), \
                 mock.patch.object(service, 'SDCARD_ROOT', str(Path(tmp) / 'nosd')):
                cfg = service.save_config({'trigger_mode': 'manual', 'consent_acknowledged': True}, base=base)
                self.assertEqual(cfg['trigger_mode'], 'manual')
                self.assertTrue(cfg['consent_acknowledged'])

                tap = service.set_volte_tap(True, volte_base=volte)
                self.assertTrue(tap['volte_tap_configured'])
                tap_off = service.set_volte_tap(False, volte_base=volte)
                self.assertFalse(tap_off['volte_tap_configured'])

                wav_file = str(Path(voice) / '20261118_120000_abcd.wav')
                w = wav_writer.StreamingWavWriter(wav_file, sample_rate=16000, channels=1, min_free_bytes=1024)
                w.write_pcm(b'\x01\x00' * 1600)
                w.close()
                service.append_recording_index(voice, {
                    'id': '20261118_120000_abcd',
                    'path': wav_file,
                    'filename': '20261118_120000_abcd.wav',
                    'started_at': 1700000000,
                    'duration_sec': 0.1,
                    'engine': 'volte_digital',
                })
                listed = service.list_recordings(base=base)
                self.assertEqual(len(listed['recordings']), 1)
                deleted = service.delete_recording('20261118_120000_abcd', base=base)
                self.assertTrue(deleted['deleted'])
                self.assertEqual(len(service.list_recordings(base=base)['recordings']), 0)


if __name__ == '__main__':
    unittest.main()
