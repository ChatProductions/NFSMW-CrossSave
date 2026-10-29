"""PS2 Black Edition layout tests, using generated synthetic saves only.

No personal save data, native PS2 assets, icons or player careers are bundled.
"""
from __future__ import annotations

import hashlib
import struct
import unittest

from converter_core import (
    REGIONS, ConversionError, _built_in_scaffold, _repair_header, parse_pc,
)
from ps2_layout import transfer_fields
from ps2_support import (
    PS2_FILE_BYTES, PS2_VITA_BYTES, PS2_FOLDER_PREFIX, parse_ps2, describe_ps2,
    pc_to_ps2, ps2_to_pc, wrap_psu, _padding_locations,
)


def fixture_pc():
    pc = bytearray(_built_in_scaffold('pc'))
    pc[0x5A31:0x5A55] = b'SMOKE'.ljust(36, b'\x00')
    pc[0x44:0x48] = b'Game'
    struct.pack_into('<I', pc, 0x48, 8)
    for pos in _padding_locations(pc):
        pc[pos] = 0xCD
    pc[0x34:0x44] = hashlib.md5(pc[0x44:0x4034]).digest()
    _repair_header(pc, '<', True)
    return parse_pc(bytes(pc))


def fixture_native(pc):
    native = bytearray(PS2_FILE_BYTES)
    native[:4] = b'20CM'
    struct.pack_into('<I', native, 4, PS2_FILE_BYTES)
    struct.pack_into('<I', native, 8, 8)
    struct.pack_into('<I', native, 0x0C, PS2_FILE_BYTES - 0x24)
    struct.pack_into('<I', native, 0x1C, 0x10D)
    struct.pack_into('<I', native, 0x20, PS2_FILE_BYTES - 0x24)
    transfer_fields(pc, native, source_format='pc', target_format='native')
    # These are fixed data-layout markers in the known SLUS-21351 save.
    native[0x5A56:0x5A59] = b'\xAA' * 3
    native[0x5C01:0x5C05] = b'\x78\x56\x34\x12'
    native[0x9D09:0x9D0D] = b'\x84\x0f\x85\x0f'
    native[0x34:0x44] = hashlib.md5(native[0x44:0x4034]).digest()
    _repair_header(native, '<', True)
    parse_ps2(bytes(native))
    return bytes(native)


def fixture_vita(pc):
    raw = bytearray(PS2_VITA_BYTES)
    struct.pack_into('<4I', raw, 0, 8, PS2_VITA_BYTES-16,
                     0x10D, PS2_VITA_BYTES-16)
    transfer_fields(pc, raw, source_format='pc', target_format='vita')
    raw[0x5BC5-20:0x5BC9-20] = b'\x78\x56\x34\x12'
    raw[0x20:0x30] = hashlib.md5(raw[0x30:0x4020]).digest()
    raw[-16:] = hashlib.md5(raw[0x20:-16]).digest()
    parse_ps2(bytes(raw))
    return bytes(raw)


def fixture_psu(native):
    name = (PS2_FOLDER_PREFIX + describe_ps2(native)['name']).encode('ascii')
    def entry(label, size, mode):
        b = bytearray(0x200)
        struct.pack_into('<H', b, 0, mode)
        struct.pack_into('<I', b, 4, size)
        b[0x40:0x40 + len(label)] = label
        return bytes(b)
    result = bytearray(entry(name, 3, 0x8427))
    result += entry(b'.', 0, 0x8427)
    result += entry(b'..', 0, 0x8427)
    result += entry(name, len(native), 0x8497)
    result += native
    result += bytes((-len(native)) % 0x400)
    return bytes(result)


class PS2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pc = fixture_pc()
        cls.native_donor = fixture_native(cls.pc)
        cls.vita_donor = fixture_vita(cls.pc)
        cls.psu_donor = fixture_psu(cls.native_donor)
        cls.native = pc_to_ps2(cls.pc, fmt='ps2file',
                               psu_template=cls.native_donor)
        cls.vita = pc_to_ps2(cls.pc, fmt='vita',
                             psu_template=cls.vita_donor)
        cls.psu = pc_to_ps2(cls.pc, fmt='psu',
                            psu_template=cls.psu_donor)

    def test_format_detection(self):
        for data, fmt, size in (
            (self.vita, 'vita', PS2_VITA_BYTES),
            (self.native, 'ps2file', PS2_FILE_BYTES),
            (self.psu, 'psu', len(self.psu_donor)),
        ):
            self.assertEqual(len(data), size)
            self.assertEqual(describe_ps2(data)['format'], fmt)
            self.assertEqual(describe_ps2(data)['name'], 'SMOKE')

    def test_native_offset_mapping(self):
        for pc_off, native_off, size, _ in REGIONS:
            # The final two formats have distinct offsets beyond 0x6219.
            self.assertEqual(self.native[native_off:native_off + size],
                             self.vita[pc_off-20:pc_off-20 + size])
        self.assertEqual(self.native[0x5C01:0x5C05], b'\x78\x56\x34\x12')
        self.assertEqual(self.native[0x9D09:0x9D0D], b'\x84\x0f\x85\x0f')

    def test_roundtrip_fields(self):
        for blob in (self.vita, self.native, self.psu):
            restored = ps2_to_pc(blob, pc_template=self.pc)
            self.assertEqual(restored, self.pc)

    def test_rename_and_psu_wrapper(self):
        converted = pc_to_ps2(self.pc, fmt='ps2file',
                              psu_template=self.native_donor,
                              new_name='ROUND')
        psu = wrap_psu(converted, self.psu_donor)
        self.assertEqual(parse_ps2(psu), converted)
        self.assertEqual(describe_ps2(psu)['name'], 'ROUND')
        self.assertEqual(len(psu), len(self.psu_donor))
        vita = pc_to_ps2(self.pc, fmt='vita',
                         psu_template=self.vita_donor,
                         new_name='ROUND')
        self.assertEqual(describe_ps2(vita)['name'], 'ROUND')

    def test_cash(self):
        for fmt, donor in [('vita', self.vita_donor),
                           ('ps2file', self.native_donor),
                           ('psu', self.psu_donor)]:
            result = pc_to_ps2(self.pc, fmt=fmt, psu_template=donor,
                               cash=123456)
            self.assertEqual(describe_ps2(result)['cash'], 123456)
            self.assertEqual(ps2_to_pc(result, pc_template=self.pc)[0x4039:0x403d],
                             struct.pack('<I', 123456))

    def test_old_alignment_rejected(self):
        damaged = bytearray(self.native)
        damaged[0x5C01:0x5C05] = b'\x00' * 4
        _repair_header(damaged, '<', True)
        with self.assertRaisesRegex(ConversionError, 'misaligned'):
            parse_ps2(bytes(damaged))

    def test_md5_validation(self):
        for blob in (self.native, self.vita):
            damaged = bytearray(blob)
            damaged[0x100] ^= 1
            with self.assertRaises(ConversionError):
                parse_ps2(bytes(damaged))

    def test_donor_required(self):
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, fmt='vita')
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, fmt='ps2file')
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, fmt='psu',
                      psu_template=self.native_donor)
        with self.assertRaises(ConversionError):
            pc_to_ps2(self.pc, fmt='vita',
                      psu_template=self.native_donor)


if __name__ == '__main__':
    unittest.main()
