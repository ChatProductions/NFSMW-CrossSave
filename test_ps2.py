"""Offline PS2 Black Edition format regression tests. No personal saves shipped."""
from __future__ import annotations
import hashlib
import struct
import unittest
from converter_core import ConversionError, _built_in_scaffold, _repair_header, parse_pc
from ps2_support import (
    PS2_FILE_BYTES, PS2_VITA_BYTES, PS2_FOLDER_PREFIX, parse_ps2, describe_ps2,
    pc_to_ps2, ps2_to_pc, wrap_psu,
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
            self.assertEqual(pc, self.pc)
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
