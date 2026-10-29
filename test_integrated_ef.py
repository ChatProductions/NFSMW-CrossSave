"""Ensure built-in original EF/EF.psu produce exactly the explicit-template output.
No player career data is included in this test.
"""
from __future__ import annotations
import hashlib
import struct
import unittest
from converter_core import _built_in_scaffold, _repair_header, parse_pc
from ps2_support import (integrated_template, pc_to_ps2, describe_ps2,
                         PS2_VITA_BYTES, PS2_FILE_BYTES)


class IntegratedEFTests(unittest.TestCase):
    def test_source_assets_are_exact(self):
        self.assertEqual(hashlib.sha256(integrated_template('vita')).hexdigest(),
            '205283cd60d266f98e97895600a6d169e9b2f84489f70dd0e3910576789e2646')
        self.assertEqual(hashlib.sha256(integrated_template('psu')).hexdigest(),
            '453116e60330026644718dbfdbd8fcc0781927207ef59cc177c037461e6263d6')
        self.assertEqual(len(integrated_template('vita')), PS2_VITA_BYTES)
        self.assertEqual(len(integrated_template('psu')),99328)

    def test_all_ps2_output_formats_use_original_templates(self):
        pc=bytearray(_built_in_scaffold('pc'))
        pc[0x5A31:0x5A55]=b'SMOKE'.ljust(36,b'\0')
        pc[0x44:0x48]=b'Game'
        struct.pack_into('<I',pc,0x48,8)
        # Same immutable platform markers as the original bundled EF profile.
        pc[0x5BC5:0x5BC9]=b'\x78\x56\x34\x12'
        pc[0x9CCD:0x9CD1]=b'\x84\x0f\x85\x0f'
        pc[0x34:0x44]=hashlib.md5(pc[0x44:0x4034]).digest()
        _repair_header(pc,'<',True)
        pc=parse_pc(bytes(pc))
        for fmt in ('vita','ps2file','psu'):
            with self.subTest(fmt=fmt):
                output=pc_to_ps2(pc,fmt=fmt)
                explicit=pc_to_ps2(pc,fmt=fmt,psu_template=integrated_template(fmt))
                self.assertEqual(output,explicit)
                self.assertEqual(describe_ps2(output)['format'],fmt)
                if fmt=='vita':self.assertEqual(len(output),PS2_VITA_BYTES)
                if fmt=='ps2file':self.assertEqual(len(output),PS2_FILE_BYTES)
                if fmt=='psu':self.assertEqual(len(output),99328)

if __name__=='__main__':unittest.main()
