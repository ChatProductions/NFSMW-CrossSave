"""Transfer career fields between PC, Vita raw, and PS2-native layouts.

The Vita port uses PC-offset little-endian career fields, with a header
20 bytes shorter than PC. Its PS2 Black Edition native export uses
GameCube-offset fields in little-endian form. The two are NOT interchangeable.

A genuine destination-format save is used as the scaffold; this module
updates only fields understood by the CrossSave v0.5 career mapping.
"""
from __future__ import annotations

from converter_core import REGIONS, ConversionError

VITA_HEADER_DELTA = 0x14


def _padding(data: bytes, kind: str, *, to_console: bool) -> bytes:
    out = bytearray(data)
    src, dst = (0xCD, 0xAA) if to_console else (0xAA, 0xCD)
    if kind == 'case':
        out[-3:] = bytes([dst]) * 3
    elif kind == 'cars':
        for i in range(0, len(out), 20):
            if out[i+18:i+20] == bytes([src]) * 2:
                out[i+18:i+20] = bytes([dst]) * 2
    elif kind == 'customizations':
        for i in range(0, len(out), 0x198):
            if out[i+0x116:i+0x118] == bytes([src]) * 2:
                out[i+0x116:i+0x118] = bytes([dst]) * 2
            if out[i+0x195:i+0x198] == bytes([src]) * 3:
                out[i+0x195:i+0x198] = bytes([dst]) * 3
    elif kind == 'pursuits':
        for i in range(0, len(out), 0x38):
            for d in (1, 10, 11):
                if out[i+d] == src:
                    out[i+d] = dst
            if out[i] == 0xff:
                for d in (*range(2, 10), *range(12, 24)):
                    if out[i+d] == src:
                        out[i+d] = dst
    return bytes(out)


def transfer_fields(source: bytes, target: bytearray, *,
                    source_format: str, target_format: str) -> None:
    """Copy transferable sections. Formats: 'pc', 'vita', 'native'."""
    allowed = {'pc', 'vita', 'native'}
    if source_format not in allowed or target_format not in allowed:
        raise ConversionError('Unknown career layout')
    for pc_off, native_off, size, kind in REGIONS:
        def offset(fmt):
            if fmt == 'native':
                return native_off
            return pc_off - (VITA_HEADER_DELTA if fmt == 'vita' else 0)
        src, dst = offset(source_format), offset(target_format)
        if src+size > len(source) or dst+size > len(target):
            raise ConversionError(f'Truncated {kind} career section')
        section = bytes(source[src:src+size])
        if (source_format == 'pc') != (target_format == 'pc'):
            section = _padding(section, kind, to_console=(target_format != 'pc'))
        target[dst:dst+size] = section
