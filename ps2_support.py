"""PS2 Black Edition (SLUS-21351) support for NFSMW CrossSave.

Three input representations are recognized:
- Vita port's extensionless 0xF4CD-byte profile (e.g. EF).
- PS2 memory-card's 0xF4E1-byte 20CM game file.
- A PSU archive with the PS2 file and its memory-card icon metadata.

PS2 output in .psu form needs a user-supplied PSU template, so the app
never redistributes the user's career, console icon, or proprietary art.
Offline structural validation does NOT imply verified in-game compatibility.
"""
from __future__ import annotations

import hashlib
import re
import struct

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
    return content


def _from_vita(data: bytes) -> bytes:
    _require(len(data) == PS2_VITA_BYTES, 'Expected 0xF4CD-byte Vita profile.')
    _require(struct.unpack_from('<4I', data, 0) ==
             (8, PS2_VITA_BYTES - 16, 0x10D, PS2_VITA_BYTES - 16)
             and data[0x10:0x20] == bytes(16),
             'Unsupported Vita PS2 Black Edition profile header.')
    _require(hashlib.md5(data[0x30:0x4020]).digest() == data[0x20:0x30],
             'Vita PS2 gameplay MD5 mismatch.')
    _require(hashlib.md5(data[0x20:-16]).digest() == data[-16:],
             'Vita PS2 profile MD5 mismatch.')
    result = bytearray(PS2_FILE_BYTES)
    struct.pack_into('<4I', result, 0, 0x4D433032, PS2_FILE_BYTES, 8,
                     PS2_FILE_BYTES - 0x24)
    struct.pack_into('<I', result, 0x1c, 0x10D)
    struct.pack_into('<I', result, 0x20, PS2_FILE_BYTES - 0x24)
    result[0x34:] = data[0x20:]
    _repair_header(result, '<', True)
    return _check_ps2_file(bytes(result))


def _to_vita(native: bytes) -> bytes:
    result = struct.pack('<4I', 8, PS2_VITA_BYTES - 16, 0x10D,
                         PS2_VITA_BYTES - 16) + bytes(16) + native[0x34:]
    _require(len(result) == PS2_VITA_BYTES, 'Vita PS2 output size mismatch.')
    _from_vita(result)
    return result


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
        b[0x429D:0x42AD] = case.ljust(13, b'\x00') + b'\xcd' * 3


def ps2_to_pc(ps2: bytes, pc_template: bytes | None = None,
              cash: int | None = None, *, new_name: str | None = None) -> bytes:
    native = parse_ps2(ps2)
    pc = bytearray(parse_pc(pc_template) if pc_template is not None
                   else _built_in_scaffold('pc'))
    pc[0x34:PS2_FILE_BYTES] = native[0x34:]
    if new_name is not None:
        _rename(pc, new_name)
    if cash is not None:
        _require(0 <= cash <= 2_000_000_000, 'Cash out of range.')
        struct.pack_into('<I', pc, 0x4039, cash)
    _repair_header(pc, '<', True)
    return parse_pc(bytes(pc))


def pc_to_ps2(pc_data: bytes, *, cash: int | None = None,
              new_name: str | None = None, fmt: str = 'vita',
              psu_template: bytes | None = None) -> bytes:
    pc = parse_pc(pc_data)
    native = bytearray(pc[:PS2_FILE_BYTES])
    struct.pack_into('<I', native, 4, PS2_FILE_BYTES)
    struct.pack_into('<I', native, 0x0c, PS2_FILE_BYTES - 0x24)
    struct.pack_into('<I', native, 0x20, PS2_FILE_BYTES - 0x24)
    if new_name is not None:
        _rename(native, new_name)
    _ps2_name(_name(native))
    if cash is not None:
        _require(0 <= cash <= 2_000_000_000, 'Cash out of range.')
        struct.pack_into('<I', native, 0x4039, cash)
    _repair_header(native, '<', True)
    result = _check_ps2_file(bytes(native))
    if fmt == 'ps2file':
        return result
    if fmt == 'vita':
        return _to_vita(result)
    if fmt == 'psu':
        _require(psu_template is not None,
                 'PSU output requires a user-provided SLUS-21351 .psu template.')
        return wrap_psu(result, psu_template)
    raise ConversionError('Unknown PS2 output format.')


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
