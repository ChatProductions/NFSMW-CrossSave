"""v0.5 edition conversion tests. These prove structural integrity, NOT regional game acceptance.

Optional command-line arguments:
    python test_regions.py /path/to/USA.gci /path/to/PCprofile

No personal save data is bundled in the release.
"""
from __future__ import annotations
from pathlib import Path
import sys

from converter_core import (
    ConversionError, GAMECUBE_REGIONS, DEFAULT_GAME_ID, GC_BLOCK_OFFSET,
    GC_MC02_BYTES, gamecube_game_id, gc_to_gc, gc_to_pc, pc_to_gc,
    parse_gci, parse_pc, describe, _built_in_scaffold,
)


def expect_rejected(fn, what):
    try:
        fn()
    except ConversionError:
        return
    raise AssertionError(f'Unexpected acceptance: {what}')


def run(gci: bytes, pc: bytes):
    assert gamecube_game_id(gci) == DEFAULT_GAME_ID
    assert parse_gci(gci)
    assert parse_pc(pc)
    native = gci[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES]
    name = describe(gci, 'gc')['name']
    for target_id in GAMECUBE_REGIONS:
        converted = gc_to_gc(gci, target_id, new_name='REGTEST' if target_id == DEFAULT_GAME_ID else None)
        assert parse_gci(converted)
        assert gamecube_game_id(converted) == target_id
        if target_id != DEFAULT_GAME_ID:
            assert converted[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES] == native
            assert describe(converted, 'gc')['name'] == name
        assert gc_to_pc(converted) == gc_to_pc(gci) if target_id != DEFAULT_GAME_ID else True
        print(f'PASS: GC {DEFAULT_GAME_ID} -> {target_id}, checksums / profile / payload')

        pc_to_region = pc_to_gc(pc, game_id=target_id)
        assert gamecube_game_id(pc_to_region) == target_id
        assert describe(pc_to_region, 'gc')['name'] == describe(pc, 'pc')['name'] + 'GC'
        assert describe(gc_to_pc(pc_to_region), 'pc')['cash'] == describe(pc, 'pc')['cash']
        print(f'PASS: PC -> {target_id} -> PC, metadata and career data')

    for target_id in GAMECUBE_REGIONS:
        if target_id == DEFAULT_GAME_ID:
            continue
        first = gc_to_gc(gci, target_id)
        back = gc_to_gc(first, DEFAULT_GAME_ID)
        assert back[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES] == native
        print(f'PASS: GC {DEFAULT_GAME_ID} -> {target_id} -> {DEFAULT_GAME_ID} native roundtrip')

    expect_rejected(lambda: gc_to_gc(gci, DEFAULT_GAME_ID), 'same edition / same name')
    expect_rejected(lambda: gc_to_gc(gci, 'NOTVALID'), 'unknown edition')
    expect_rejected(lambda: pc_to_gc(pc, game_id='GOWJ69'), 'unverified alternate Japanese edition')
    wrong_company = bytearray(gci)
    wrong_company[4:6] = b'13'
    expect_rejected(lambda: parse_gci(bytes(wrong_company)), 'unsupported company code')
    tampered = bytearray(gc_to_gc(gci, 'GOWP69'))
    tampered[GC_BLOCK_OFFSET + 0x80] ^= 1
    expect_rejected(lambda: parse_gci(bytes(tampered)), 'tampered gameplay')
    print('PASS: Rejected unsupported editions and corrupted saves')


if __name__ == '__main__':
    if len(sys.argv) == 3:
        run(Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes())
    else:
        print('Pass a valid USA .gci and PC save to run the regional conversion regression suite.')
