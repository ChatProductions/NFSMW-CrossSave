"""Regression tests for v1.0 (includes historical v0.2 repair regression). Optional fixtures are not distributed."""
from __future__ import annotations
import sys
import struct
from pathlib import Path
from converter_core import (
    ConversionError, gc_to_pc, pc_to_gc, repair_v02_gci,
    describe, parse_pc, parse_gci, _built_in_scaffold, _asset,
)


def reject(call, message):
    try:
        call()
    except ConversionError:
        return
    raise AssertionError(message)


def main():
    assert len(_built_in_scaffold('pc')) == 0xF86C
    assert len(_built_in_scaffold('gc')) == 0xF4E1
    assert len(_asset('gc_media.z')) == 0x2000
    for name in ('NAME','UTKU','MW-'):
        for platform in ('pc','gc'):
            assert name.encode() not in _built_in_scaffold(platform)
    print('PASS: Sanitized platform scaffolds')
    if len(sys.argv) == 1:
        print('Optional fixture tests: python self_test.py original.gci verified_PC broken_v02.gci')
        return 0
    if len(sys.argv) != 4:
        print('Usage: python self_test.py original.gci verified_PC broken_v02.gci')
        return 2
    original, expected, broken = (Path(arg).read_bytes() for arg in sys.argv[1:])
    assert describe(original,'gc')['name'] == 'UTKU'
    cash=describe(expected,'pc')['cash']
    assert gc_to_pc(original,cash=cash) == expected
    print('PASS: Original GameCube -> PC byte-identical to known-good career')
    reject(lambda: parse_gci(broken),'Old v0.2 invalid media prelude was accepted')
    repaired=repair_v02_gci(broken,'UTK')
    assert describe(repaired,'gc')['name'] == 'UTK'
    assert describe(repaired,'gc')['cash'] == int.from_bytes(broken[0x2090+0x4039:0x2090+0x403d],'big')
    assert repaired[8:0x28].split(b'\0',1)[0] == b'NFSMWUTK'
    assert repaired[0x70:0x90].split(b'\0',1)[0] == b'UTK'
    assert repaired[0x40:0x50] != bytes(16)
    assert parse_gci(repaired)
    assert repaired[0x2090+0x34:0x2090+0x4034] == broken[0x2090+0x34:0x2090+0x4034]
    print('PASS: Repair v0.2 GCI, preserve gameplay, distinct internal identity')
    safe=pc_to_gc(expected)
    assert describe(safe,'gc')['name'] == 'UTKUGC'
    assert safe[8:0x28].split(b'\0',1)[0] != original[8:0x28].split(b'\0',1)[0]
    assert safe[0x40:0x50] != bytes(16)
    assert gc_to_pc(safe) != expected # name intentionally changed
    assert describe(gc_to_pc(safe),'pc')['cash'] == cash
    print('PASS: PC -> GameCube defaults to collision-safe internal identity')
    reject(lambda: pc_to_gc(expected,new_name='UTKU'),'Duplicate internal name accepted')
    assert gc_to_pc(pc_to_gc(expected,new_name='UTKU',allow_same_name=True)) == expected
    print('PASS: Explicit same-name roundtrip remains exact for regression testing')
    for value in (0,35050,250000,2000000000):
        g=pc_to_gc(gc_to_pc(original,cash=value),new_name='UTK')
        assert describe(g,'gc')['cash'] == value
        assert describe(g,'gc')['career_started']
    print('PASS: Cash editing and career flags')
    altered=bytearray(safe)
    altered[0x4c]^=1
    reject(lambda: parse_gci(bytes(altered)),'Bad GameCube media checksum accepted')
    altered=bytearray(safe)
    altered[8:0x28]=b'NFSMWUTKU'.ljust(32,b'\0')
    reject(lambda: parse_gci(bytes(altered)),'Mismatched internal identity accepted')
    print('PASS: GCI metadata integrity checks')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
