"""GUI behavior regression tests: PS2 template selection and error guidance.

These tests avoid opening windows and use source-only fixtures. They guard
against v0.7.2's disabled Advanced checkbox / 'uncheck Advanced' contradiction.
"""
from __future__ import annotations

import runpy
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from converter_core import ConversionError
from test_ps2 import fixture_pc, fixture_vita, fixture_native, fixture_psu


GUI = runpy.run_path(str(Path(__file__).with_name('converter_gui.pyw')))
CrossSaveApp = GUI['CrossSaveApp']
ps2_template_requirement = GUI['ps2_template_requirement']
verify_ps2_destination_template = GUI['verify_ps2_destination_template']


class Var:
    def __init__(self, value=''):
        self.value = value

    def get(self):
        return self.value


class GUITemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pc = fixture_pc()
        cls.vita = fixture_vita(pc)
        cls.native = fixture_native(pc)
        cls.psu = fixture_psu(cls.native)

    def test_destination_template_format_combinations(self):
        self.assertEqual(verify_ps2_destination_template(self.vita, 'vita'), 'vita')
        self.assertEqual(verify_ps2_destination_template(self.native, 'ps2file'), 'ps2file')
        self.assertEqual(verify_ps2_destination_template(self.psu, 'ps2file'), 'psu')
        self.assertEqual(verify_ps2_destination_template(self.psu, 'psu'), 'psu')
        for wrong_blob, output_type in [
            (self.psu, 'vita'), (self.vita, 'psu'),
            (self.vita, 'ps2file'), (self.native, 'psu'),
        ]:
            with self.subTest(fmt=output_type, size=len(wrong_blob)):
                with self.assertRaisesRegex(ConversionError, 'Wrong destination template'):
                    verify_ps2_destination_template(wrong_blob, output_type)

    def test_donor_free_vita_source_and_required_psu(self):
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / 'career.gci'
            source.write_bytes(b'file-size-not-relevant-to-ui-path-tests')
            state = SimpleNamespace(
                direction='gc_ps2',
                gc_in=Var(str(source)),
                pc_in=Var(),
                ps2_in=Var(),
                ps2_format_choice=Var('Vita port profile (extensionless)'),
                template_path=Var(''),
                use_template=Var(False),
                output_vars={'gc_ps2': Var(work)},
            )
            # No donor file is required for the requested extensionless Vita.
            chosen = CrossSaveApp._inputs(state)
            self.assertEqual(chosen[0], source)
            self.assertIsNone(chosen[2])
            self.assertIsNone(chosen[3])
            self.assertEqual(chosen[-1], 'gc')

            # Advanced mode remains optional for Vita compatibility testing.
            donor = Path(work) / 'EF'
            donor.write_bytes(self.vita)
            state.use_template = Var(True)
            state.template_path = Var(str(donor))
            with_donor = CrossSaveApp._inputs(state)
            self.assertEqual(with_donor[3], self.vita)

            # Native PS2 and PSU still require their console metadata.
            state.ps2_format_choice = Var('PS2 PSU archive (built-in EF.psu)')
            state.use_template = Var(True)
            state.template_path = Var('')
            # Engine supplies original EF.psu internally.
            state.use_template = Var(False)
            empty_psu = CrossSaveApp._inputs(state)
            self.assertIsNone(empty_psu[3])

            donor = Path(work) / 'EF.psu'
            donor.write_bytes(self.psu)
            state.template_path = Var(str(donor))
            state.use_template = Var(True)
            output = CrossSaveApp._inputs(state)
            self.assertEqual(output[3], self.psu)

    def test_pc_gc_existing_donor_free_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / 'sample.gci'
            source.write_bytes(b'source')
            state = SimpleNamespace(
                direction='gc_pc', gc_in=Var(str(source)),
                pc_in=Var(), ps2_in=Var(), template_path=Var(''),
                use_template=Var(False), output_vars={'gc_pc': Var(work)},
            )
            info = CrossSaveApp._inputs(state)
            self.assertIsNone(info[2])
            self.assertIsNone(info[3])

    def test_distinct_output_format_guidance(self):
        self.assertIn('integrated', ps2_template_requirement('vita'))
        self.assertIn('game file', ps2_template_requirement('ps2file'))
        self.assertIn('.psu', ps2_template_requirement('psu'))
        with self.assertRaises(ConversionError):
            ps2_template_requirement('unknown')


if __name__ == '__main__':
    unittest.main()
