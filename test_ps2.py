"""Offline PS2 Black Edition format regression tests. No personal saves shipped."""
from __future__ import annotations
import hashlib
import struct
import unittest
from converter_core import ConversionError, _built_in_scaffold, _repair_header, parse_pc
from ps2_support import (
    PS2_FILE_BYTES, PS2_VITA_BYTES, PS2_FOLDER_PREFIX, parse_ps2, describe_ps2,
    pc_to_ps2, ps2_to_pc, wrap_psu, _padding_locations, _translate_padding,
)


def test_pc_profile():
    pc = bytearray(_built_in_scaffold('pc'))
    pc[0x5a31:0x5a55] = b'SMOKE'.ljust(36, b'\x00')
    pc[0x44:0x48] = b'Game'
    struct.pack_into('<I', pc, 0x48, 8)
    pc[0x34:0x44] = hashlib.md5(pc[0x44:0x4034]).digest()
    _repair_header(pc, '<', True)
    return parse_pc(bytes(pc))


def test_psu(native):
    name = (PS2_FOLDER_PREFIX + describe_ps2(native)['name']).encode('ascii')
    # Generated, neutral PSU for archive-structure testing; no proprietary icons.
    def header(label, size, mode):
        h = bytearray(0x200)
        struct.pack_into('<H', h, 0, mode)
        struct.pack_into('<I', h, 4, size)
        h[0x40:0x40+len(label)] = label
        return bytes(h)
    result = bytearray(header(name, 3, 0x8427))
    result += header(b'.', 0, 0x8427)
    result += header(b'..', 0, 0x8427)
    result += header(name, len(native), 0x8497)
    result += native
    result += bytes((-len(native)) % 0x400)
    return bytes(result)


class PS2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pc = test_pc_profile()
        cls.vita = pc_to_ps2(cls.pc)
        cls.native = pc_to_ps2(cls.pc, fmt='ps2file')
        cls.psu = test_psu(cls.native)

    def test_representation_sizes(self):
        self.assertEqual(len(self.vita), PS2_VITA_BYTES)
        self.assertEqual(len(self.native), PS2_FILE_BYTES)
        for blob, fmt in ((self.vita, 'vita'), (self.native, 'ps2file'), (self.psu, 'psu')):
            self.assertEqual(describe_ps2(blob)['format'], fmt)
            self.assertEqual(describe_ps2(blob)['name'], 'SMOKE')

    def test_lossless_ps2_pc_ps2_roundtrip(self):
        for blob in (self.vita, self.native, self.psu):
            pc = ps2_to_pc(blob, pc_template=self.pc)
            # The native PS2 checksum occupies bytes used for PC-specific
            # trailing fields; preserve career data and verify PS2 exactness.
            self.assertEqual(pc[0x34:PS2_FILE_BYTES-16],
                             self.pc[0x34:PS2_FILE_BYTES-16])
            self.assertEqual(pc_to_ps2(pc, fmt='ps2file'), self.native)

    def test_psu_template_copy_and_rename(self):
        named = pc_to_ps2(self.pc, fmt='ps2file', new_name='ROUND')
        archive = wrap_psu(named, self.psu)
        self.assertEqual(parse_ps2(archive), named)
        self.assertEqual(describe_ps2(archive)['name'], 'ROUND')
        self.assertEqual(len(archive), len(self.psu))
        self.assertEqual(parse_ps2(self.psu), self.native)

    def test_cash_override(self):
        out = pc_to_ps2(self.pc, cash=123456)
        self.assertEqual(describe_ps2(out)['cash'], 123456)
        restored = ps2_to_pc(out, pc_template=self.pc)
        self.assertEqual(restored[0x4039:0x403d], struct.pack('<I', 123456))

    def test_platform_specific_padding_and_tail(self):
        # The PC and PS2 career structures share offsets, but not padding.
        pc = bytearray(self.pc)
        for pos in _padding_locations(pc):
            pc[pos] = 0xCD
        _repair_header(pc, '<', True)
        output = pc_to_ps2(bytes(pc), fmt='ps2file')
        self.assertTrue(all(output[pos] != 0xCD for pos in _padding_locations(output)))
        self.assertEqual(output[0x429D + 13:0x429D + 16], b'\xAA'*3)
        self.assertEqual(output[0xF494:0xF4D1], bytes(0xF4D1 - 0xF494))
        restored = ps2_to_pc(output, pc_template=bytes(pc))
        self.assertEqual(restored[0x429D + 13:0x429D + 16], b'\xCD'*3)
        self.assertTrue(all(restored[pos] != 0xAA for pos in _padding_locations(restored)))

    def test_v07_corrupted_padding_is_rejected(self):
        # The old v0.7 converter calculated valid MD5s for invalid PS2 pads.
        invalid = bytearray(self.native)
        invalid[0x429D + 13:0x429D + 16] = b'\xCD'*3
        invalid[0x5A56:0x5A59] = b'\xCD'*3
        _repair_header(invalid, '<', True)
        with self.assertRaisesRegex(ConversionError, 'PC-specific padding'):
            parse_ps2(bytes(invalid))

    def test_corruption_rejected(self):
        for blob in (self.vita, self.native):
            corrupted = bytearray(blob)
            corrupted[0x100] ^= 1
            with self.assertRaises(ConversionError):
                parse_ps2(bytes(corrupted))
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, fmt='psu')
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, new_name='A'*26)


if __name__ == '__main__':
    unittest.main()
