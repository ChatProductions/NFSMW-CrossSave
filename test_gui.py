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

    def test_missing_template_message_is_actionable(self):
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
                use_template=Var(True),
                output_vars={'gc_ps2': Var(work)},
            )
            with self.assertRaises(ConversionError) as caught:
                CrossSaveApp._inputs(state)
            msg = str(caught.exception)
            self.assertIn('REQUIRED', msg)
            self.assertIn('Browse destination save', msg)
            self.assertIn('extensionless', msg)
            self.assertNotIn('uncheck Advanced', msg)

            destination = Path(work) / 'EF'
            destination.write_bytes(self.vita)
            state.template_path = Var(str(destination))
            source_file, source_bytes, donor_path, donor_bytes, folder, source_kind = CrossSaveApp._inputs(state)
            self.assertEqual(source_file, source)
            self.assertEqual(donor_bytes, self.vita)
            self.assertEqual(donor_path, destination)
            self.assertEqual(source_kind, 'gc')

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
        self.assertIn('Vita-port profile', ps2_template_requirement('vita'))
        self.assertIn('game file', ps2_template_requirement('ps2file'))
        self.assertIn('.psu', ps2_template_requirement('psu'))
        with self.assertRaises(ConversionError):
            ps2_template_requirement('unknown')


if __name__ == '__main__':
    unittest.main()
