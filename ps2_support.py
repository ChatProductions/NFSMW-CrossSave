"""PS2 Black Edition (SLUS-21351) support for NFSMW CrossSave.

Three input representations are recognized:
- Vita port's extensionless 0xF4CD-byte profile (e.g. EF).
- PS2 memory-card's 0xF4E1-byte 20CM game file.
- A PSU archive with the PS2 file and its memory-card icon metadata.

Vita raw output can be generated donor-free from CrossSave's already
bundled, sanitized PC platform scaffold. Optional genuine Vita templates
remain supported for compatibility checks. Complete PS2 .psu packaging
still requires metadata/icon assets from the user's own .psu export.
Offline structural validation does NOT imply verified in-game compatibility.
"""
from __future__ import annotations

import hashlib
import re
import struct

from ps2_layout import transfer_fields

from converter_core import (
    ConversionError, ea_crc32, parse_pc, pc_to_gc, gc_to_pc,
    _built_in_scaffold, _repair_header, _name, _valid_gc_name,
)

PS2_TITLE_ID = 'SLUS-21351'
PS2_FOLDER_PREFIX = 'BASLUS-21351-'
PS2_FILE_BYTES = 0xF4E1
PS2_VITA_BYTES = 0xF4CD
PS2_MAX_NAME = 32 - len(PS2_FOLDER_PREFIX)


def _require(ok: bool, message: str):
    if not ok:
        raise ConversionError(message)


def _ps2_name(name: str) -> str:
    result = _valid_gc_name(name)
    _require(len(result) <= PS2_MAX_NAME,
             f'PS2 profile name cannot exceed {PS2_MAX_NAME} characters.')
    return result



# PC and PS2 use the same little-endian career offsets but different
# fixed padding sentinels: PC uses CD, PS2 uses AA. In v0.7, raw PC
# records were copied directly into Vita profiles, producing internally
# checksummed saves which the PS2 game could nevertheless reject.
#
# These locations are data-independent structural fields, identified
# by comparing genuine PS2 Black Edition SLUS-21351 and PC/GC saves.
def _padding_locations(data: bytes):
    yield from range(0x429D + 13, 0x429D + 16)  # case identifier padding
    # 26 eight-byte garage statistic records followed by empty record slots
    for i in range(26):
        p = 0x5A54 + i * 8 + 2
        yield from range(p, p + 3)
    yield from range(0x5B21, 0x5B41)
    for p, size in ((0x5B52, 3), (0x5B5B, 2), (0x5BB0, 1), (0x5BC4, 1)):
        yield from range(p, p + size)
    # 200 car database records, including the first 81 scaffold records
    for i in range(200):
        p = 0x5BC5 + i * 20 + 18
        yield from range(p, p + 2)
    # All 75 customizations, not only the final 44 copied by the GC core
    for i in range(75):
        p = 0x6B65 + i * 0x198
        yield from range(p + 0x116, p + 0x118)
        yield from range(p + 0x195, p + 0x198)
    for i in range(25):
        p = 0xE2ED + i * 0x38
        for d in (1, 10, 11):
            yield p + d
        if data[p] == 0xff:  # unused pursuit slot
            for d in (*range(2, 10), *range(12, 24)):
                yield p + d


def _translate_padding(data: bytearray, *, to_ps2: bool) -> int:
    # Sanitized source scaffolds may have zero-filled structural padding.
    # Normalize every known reserved byte, not only bytes already set CD/AA.
    dest = 0xAA if to_ps2 else 0xCD
    count = 0
    for p in _padding_locations(data):
        if data[p] != dest:
            data[p] = dest
            count += 1
    return count


def _neutral_vita_scaffold() -> bytearray:
    """Construct an extensionless Vita profile from existing neutral assets.

    The original CrossSave PC scaffold contains no personal career data.
    The Vita profile uses the PC-aligned layout with a 20-byte-shorter
    header, and AA platform padding instead of the PC's CD sentinels.
    This deliberately does NOT embed EF, its hashes, or any user save.
    """
    source = bytearray(_built_in_scaffold('pc')[:PS2_FILE_BYTES])
    _require(len(source) == PS2_FILE_BYTES,
             'Built-in PC scaffold cannot initialize Vita profile.')
    _translate_padding(source, to_ps2=True)
    raw = bytearray(PS2_VITA_BYTES)
    struct.pack_into('<4I', raw, 0, 8, PS2_VITA_BYTES - 16,
                     0x10D, PS2_VITA_BYTES - 16)
    raw[0x20:] = source[0x34:PS2_FILE_BYTES]
    _require(raw[0x5BC5-20:0x5BC9-20] == b'\x78\x56\x34\x12',
             'Built-in platform scaffold lacks the Vita car database.')
    _require(raw[0x6B65-20:0x6B69-20] == b'\xDA\x13\xDB\x13',
             'Built-in platform scaffold lacks the static car customizations.')
    # The profile MD5 is recomputed after inserting the real career.
    raw[-16:] = bytes(16)
    return raw


def _check_ps2_platform_fields(content: bytes):
    # The v0.7 output had valid MD5s but carried PC-only CD sentinels.
    _require(content[0x429D + 13:0x429D + 16] == bytes([0xAA]) * 3
             and content[0x5A56:0x5A59] == bytes([0xAA]) * 3,
             'PS2 profile has PC-specific padding (v0.7 bug). '
             'Reconvert using v0.7.1 or repair the existing profile.')


def _check_ps2_file(content: bytes) -> bytes:
    _require(len(content) == PS2_FILE_BYTES, 'Expected 0xF4E1-byte PS2 Black Edition game file.')
    _require(content[:4] == b'20CM', 'PS2 game file has incorrect 20CM signature.')
    _require(struct.unpack_from('<I', content, 4)[0] == PS2_FILE_BYTES,
             'Invalid PS2 file length.')
    _require(struct.unpack_from('<I', content, 8)[0] == 8 and
             struct.unpack_from('<I', content, 0x0c)[0] == PS2_FILE_BYTES - 0x24 and
             struct.unpack_from('<I', content, 0x20)[0] == PS2_FILE_BYTES - 0x24,
             'Unsupported PS2 file header.')
    _require(content[0x44:0x48] == b'Game' and
             struct.unpack_from('<I', content, 0x48)[0] == 8,
             'Unsupported PS2 gameplay format.')
    _require(hashlib.md5(content[0x44:0x4034]).digest() == content[0x34:0x44],
             'PS2 gameplay MD5 mismatch.')
    _require(hashlib.md5(content[0x34:-16]).digest() == content[-16:],
             'PS2 profile MD5 mismatch.')
    for field, start, end in ((0x10, 0x1c, 0x24),
                              (0x14, 0x24, len(content)),
                              (0x18, 0, 0x18)):
        _require(struct.unpack_from('<I', content, field)[0] == ea_crc32(content[start:end]),
                 f'PS2 header CRC mismatch at 0x{field:X}.')
    _ps2_name(_name(content))
    _check_ps2_platform_fields(content)
    # These section markers are identical in the original SLUS-21351
    # export and the equivalent genuine Vita save, after accounting for
    # the 0x3C native section shift. v0.7.1 wrote them at PC offsets.
    _require(content[0x5C01:0x5C05] == b'\x78\x56\x34\x12',
             'PS2-native garage layout is misaligned (v0.7.1 output).')
    _require(content[0x9D09:0x9D0D] == b'\x84\x0f\x85\x0f',
             'PS2-native customization layout is misaligned.')
    return content


def _from_vita(data: bytes) -> bytes:
    """Inspect a Vita raw save using a virtual header, without treating it
    as the shifted native PS2 layout. Use original raw bytes for conversion.
    """
    _require(len(data) == PS2_VITA_BYTES, 'Expected 0xF4CD-byte Vita profile.')
    _require(struct.unpack_from('<4I', data, 0) ==
             (8, PS2_VITA_BYTES - 16, 0x10D, PS2_VITA_BYTES - 16)
             and data[0x10:0x20] == bytes(16),
             'Unsupported Vita profile header.')
    _require(data[0x30:0x34] == b'Game' and
             struct.unpack_from('<I', data, 0x34)[0] == 8,
             'Unsupported Vita gameplay version.')
    _require(hashlib.md5(data[0x30:0x4020]).digest() == data[0x20:0x30],
             'Vita gameplay MD5 mismatch.')
    _require(hashlib.md5(data[0x20:-16]).digest() == data[-16:],
             'Vita profile MD5 mismatch.')
    _require(data[0x5BC5-20:0x5BC9-20] == b'\x78\x56\x34\x12',
             'Vita garage layout is misaligned.')
    virtual = bytearray(PS2_FILE_BYTES)
    struct.pack_into('<4I', virtual, 0, 0x4D433032, PS2_FILE_BYTES,
                     8, PS2_FILE_BYTES - 0x24)
    struct.pack_into('<I', virtual, 0x1C, 0x10D)
    struct.pack_into('<I', virtual, 0x20, PS2_FILE_BYTES - 0x24)
    virtual[0x34:] = data[0x20:]
    _ps2_name(_name(virtual))
    # Not a true native PS2 game file: only usable for inspection.
    return bytes(virtual)


def _rename_vita(raw: bytearray, name: str):
    name = _ps2_name(name)
    raw[0x5A31-20:0x5A55-20] = name.encode('ascii').ljust(36, b'\x00')
    p = 0x429D - 20
    old = raw[p:p+16].split(b'\x00', 1)[0].decode('ascii', 'ignore')
    match = re.match(r'^(MW-\d+-)', old)
    if match:
        case = (match.group(1) + name[:4] + 'XXX')[:12].encode('ascii')
        raw[p:p+16] = case.ljust(13, b'\x00') + b'\xAA' * 3


def _entries(psu: bytes):
    _require(len(psu) >= 0x800, 'PSU archive is truncated.')
    count = int.from_bytes(psu[4:8], 'little')
    _require(3 <= count <= 32, 'Unsupported PSU directory size.')
    _require(int.from_bytes(psu[0:2], 'little') & 0x0020,
             'PSU does not start with a directory.')
    pos = 0x200
    found = []
    for _ in range(count):
        _require(pos + 0x200 <= len(psu), 'Truncated PSU directory entry.')
        try:
            name = psu[pos+0x40:pos+0x60].split(b'\x00', 1)[0].decode('ascii', 'strict')
        except UnicodeDecodeError as exc:
            raise ConversionError('PSU contains a non-ASCII directory name.') from exc
        length = struct.unpack_from('<I', psu, pos+4)[0]
        body = pos + 0x200
        _require(body + length <= len(psu), f'Truncated PSU entry: {name}')
        found.append((name, pos, body, length))
        pos = body + ((length + 0x3ff) & ~0x3ff)
    return found


def _extract_psu(data: bytes) -> bytes:
    try:
        folder = data[0x40:0x60].split(b'\x00', 1)[0].decode('ascii', 'strict')
    except UnicodeDecodeError as exc:
        raise ConversionError('PSU directory name is not ASCII.') from exc
    _require(folder.startswith(PS2_FOLDER_PREFIX),
             'Expected PS2 Black Edition SLUS-21351 PSU directory.')
    matching = [e for e in _entries(data) if e[0] == folder]
    _require(len(matching) == 1, 'PSU must have exactly one matching career file.')
    _, _, offset, length = matching[0]
    _require(length == PS2_FILE_BYTES, 'Unexpected PS2 career file length in PSU.')
    native = _check_ps2_file(data[offset:offset+length])
    _require(_name(native) == folder[len(PS2_FOLDER_PREFIX):],
             'PSU folder and internal profile names do not match.')
    return native


def detect_ps2_format(data: bytes) -> str:
    if len(data) == PS2_VITA_BYTES:
        _from_vita(data)
        return 'vita'
    if len(data) == PS2_FILE_BYTES:
        _check_ps2_file(data)
        return 'ps2file'
    _extract_psu(data)
    return 'psu'


def parse_ps2(data: bytes) -> bytes:
    fmt = detect_ps2_format(data)
    if fmt == 'vita':
        return _from_vita(data)
    if fmt == 'ps2file':
        return data
    return _extract_psu(data)


def describe_ps2(data: bytes):
    native = parse_ps2(data)
    return {
        'name': _name(native),
        'game_id': PS2_TITLE_ID,
        'format': detect_ps2_format(data),
        'cash': int.from_bytes(native[0x4039:0x403d], 'little'),
        'blacklist': native[0x4038],
        'career_started': bool(int.from_bytes(native[0x403f:0x4043], 'little') & 1),
        'race_entries': int.from_bytes(native[0x42ad:0x42b1], 'little'),
        'gameplay_version': int.from_bytes(native[0x48:0x4c], 'little'),
    }


def _rename(b: bytearray, name: str):
    name = _ps2_name(name)
    b[0x5A31:0x5A55] = name.encode('ascii').ljust(36, b'\x00')
    old = b[0x429D:0x42AD].split(b'\x00', 1)[0].decode('ascii', 'ignore')
    match = re.match(r'^(MW-\d+-)', old)
    if match:
        case = (match.group(1) + name[:4] + 'XXX')[:12].encode('ascii')
        b[0x429D:0x42AD] = case.ljust(13, b'\x00') + b'\xaa' * 3


def ps2_to_pc(ps2: bytes, pc_template: bytes | None = None,
              cash: int | None = None, *, new_name: str | None = None) -> bytes:
    fmt = detect_ps2_format(ps2)
    native = parse_ps2(ps2) if fmt != 'vita' else None
    pc = bytearray(parse_pc(pc_template) if pc_template is not None
                   else _built_in_scaffold('pc'))
    transfer_fields(ps2 if fmt == 'vita' else native, pc,
                    source_format='vita' if fmt == 'vita' else 'native',
                    target_format='pc')
    if new_name is not None:
        name = _valid_gc_name(new_name)
        pc[0x5A31:0x5A55] = name.encode('ascii').ljust(36, b'\x00')
    if cash is not None:
        _require(0 <= cash <= 2_000_000_000, 'Cash out of range.')
        struct.pack_into('<I', pc, 0x4039, cash)
    _repair_header(pc, '<', True)
    return parse_pc(bytes(pc))


def pc_to_ps2(pc_data: bytes, *, cash: int | None = None,
              new_name: str | None = None, fmt: str = 'vita',
              psu_template: bytes | None = None) -> bytes:
    """Convert PC/Vita (unshifted) to correctly shifted PS2-native save.

    Vita raw output is donor-free by default using the existing neutral
    PC platform scaffold. A real Vita profile can still be supplied as an
    optional template. PS2-native/PSU output retains template requirements.
    """
    pc = parse_pc(pc_data)
    if psu_template is None:
        psu_template = integrated_template(fmt)
    name = _ps2_name(new_name if new_name is not None else _name(pc))
    if fmt == 'vita':
        if psu_template is None:
            raw = _neutral_vita_scaffold()
        else:
            _require(detect_ps2_format(psu_template) == 'vita',
                     'Optional Vita template must be an extensionless '
                     '62,669-byte profile from the Vita port.')
            raw = bytearray(psu_template)
        transfer_fields(pc, raw, source_format='pc', target_format='vita')
        _rename_vita(raw, name)
        if cash is not None:
            _require(0 <= cash <= 2_000_000_000, 'Cash out of range.')
            struct.pack_into('<I', raw, 0x4039-20, cash)
        raw[0x20:0x30] = hashlib.md5(raw[0x30:0x4020]).digest()
        raw[-16:] = hashlib.md5(raw[0x20:-16]).digest()
        _from_vita(bytes(raw))
        _require(_name(_from_vita(bytes(raw))) == name,
                 'Vita name verification failed.')
        return bytes(raw)
    _require(fmt in ('ps2file', 'psu'), 'Unknown PS2 destination format.')
    _require(psu_template is not None,
             'Native PS2 game files and PSU archives still require a genuine '
             'PS2 Black Edition destination template. Choose Vita port '
             'profile (extensionless) for donor-free output.')
    template_format = detect_ps2_format(psu_template)
    _require(template_format in ('ps2file', 'psu'),
             'PS2 game-file/PSU output requires an existing native PS2 '
             'Black Edition file or .psu export as Advanced template.')
    native = bytearray(parse_ps2(psu_template))
    transfer_fields(pc, native, source_format='pc', target_format='native')
    _rename(native, name)
    if cash is not None:
        _require(0 <= cash <= 2_000_000_000, 'Cash out of range.')
        struct.pack_into('<I', native, 0x4039, cash)
    _repair_header(native, '<', True)
    output = _check_ps2_file(bytes(native))
    if fmt == 'ps2file':
        return output
    _require(template_format == 'psu',
             'For full PSU output, use a complete .psu template.')
    return wrap_psu(output, psu_template)


def wrap_psu(native: bytes, template: bytes) -> bytes:
    native = _check_ps2_file(native)
    original = _extract_psu(template)
    source_folder = PS2_FOLDER_PREFIX + _name(original)
    target_folder = PS2_FOLDER_PREFIX + _name(native)
    original_entry = [e for e in _entries(template) if e[0] == source_folder][0]
    _, entry_pos, body_pos, body_length = original_entry
    _require(body_length == len(native), 'Unexpected PS2 template file size.')
    result = bytearray(template)
    encoded = target_folder.encode('ascii').ljust(32, b'\x00')
    result[0x40:0x60] = encoded
    result[entry_pos+0x40:entry_pos+0x60] = encoded
    result[body_pos:body_pos+len(native)] = native
    _require(_extract_psu(bytes(result)) == native, 'PSU output verification failed.')
    return bytes(result)


def ps2_to_gc(ps2: bytes, *, game_id: str, new_name: str | None = None,
              cash: int | None = None, pc_template: bytes | None = None,
              gc_template: bytes | None = None) -> bytes:
    pc = ps2_to_pc(ps2, pc_template=pc_template)
    return pc_to_gc(pc, gc_template=gc_template, game_id=game_id,
                    new_name=new_name, cash=cash)


def gc_to_ps2(gci: bytes, *, cash: int | None = None,
              new_name: str | None = None, fmt: str = 'vita',
              pc_template: bytes | None = None,
              psu_template: bytes | None = None) -> bytes:
    pc = gc_to_pc(gci, pc_template=pc_template)
    return pc_to_ps2(pc, cash=cash, new_name=new_name,
                     fmt=fmt, psu_template=psu_template)


# Built in from the exact EF and BASLUS-21351-EF.psu files supplied by
# the user and explicitly authorized for publication. No sanitization.
INTEGRATED_TEMPLATE_SHA256 = {
    'vita': '205283cd60d266f98e97895600a6d169e9b2f84489f70dd0e3910576789e2646',
    'psu': '453116e60330026644718dbfdbd8fcc0781927207ef59cc177c037461e6263d6',
}


def integrated_template(fmt: str) -> bytes:
    """Load an unchanged EF / EF.psu bundled via PyInstaller assets."""
    import sys
    from pathlib import Path
    if fmt not in ('vita', 'ps2file', 'psu'):
        raise ConversionError('Unsupported PS2 output format.')
    kind = 'vita' if fmt == 'vita' else 'psu'
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    fname = 'EF' if kind == 'vita' else 'BASLUS-21351-EF.psu'
    try:
        raw = (root/'assets'/fname).read_bytes()
    except OSError as exc:
        raise ConversionError('Missing bundled EF template: ' + fname) from exc
    if hashlib.sha256(raw).hexdigest() != INTEGRATED_TEMPLATE_SHA256[kind]:
        raise ConversionError('Bundled EF template failed original SHA-256 verification.')
    return raw
