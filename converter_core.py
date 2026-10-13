"""Need for Speed: Most Wanted (2005) PC <-> GameCube (GCI) save converter.

Independent, non-commercial save format research implementation.
Uses neutral built-in platform scaffolds; no external donor save required.
An optional destination-platform save can still be supplied for compatibility.

Save-layout research references:
- https://github.com/dbalatoni13/nfsmw (reverse-engineered game structures)
- https://github.com/sprintstate/nfs-mw-save-editor (console/PC layout research)
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import struct
from pathlib import Path
from datetime import datetime, timezone
import zlib
import re

PC_BYTES = 0xF86C
GC_MC02_BYTES = 0xF4E1
GC_GCI_BYTES = 0x12040
GC_BLOCK_OFFSET = 0x2090

# Recognized retail GameCube disc IDs, not claims of tested save compatibility.
# Only GOWE69 has been verified against an actual in-game career save.
GAMECUBE_REGIONS = {
    'GOWE69': 'USA (NTSC-U, English)',
    'GOWP69': 'Europe (PAL, English)',
    'GOWD69': 'Europe (PAL, German)',
    'GOWF69': 'Europe (PAL, French)',
    'GOWJ13': 'Japan (NTSC-J, Japanese)',
}
DEFAULT_GAME_ID = 'GOWE69'


def _valid_game_id(game_id: str) -> str:
    game_id = game_id.strip().upper()
    _require(game_id in GAMECUBE_REGIONS,
             f'Unsupported GameCube edition {game_id!r}. Choose a listed retail game ID.')
    return game_id


def gamecube_game_id(data: bytes) -> str:
    _require(len(data) == GC_GCI_BYTES, 'Expected a 0x12040-byte GameCube .gci file')
    game_id = data[:6].decode('ascii', errors='replace')
    return _valid_game_id(game_id)


class ConversionError(ValueError):
    pass


def _require(cond, message):
    if not cond:
        raise ConversionError(message)


def _flip(data: bytearray, pos: int, length: int):
    data[pos:pos+length] = data[pos:pos+length][::-1]


def _swap_fields(data: bytes, fields: list[tuple[int,int]]) -> bytes:
    result = bytearray(data)
    for pos, length in fields:
        _flip(result, pos, length)
    return bytes(result)


def _u32_array(data: bytes) -> bytes:
    _require(len(data) % 4 == 0, 'A 32-bit region is misaligned')
    return b''.join(data[k:k+4][::-1] for k in range(0,len(data),4))


@lru_cache(maxsize=1)
def _crc_table():
    tab=[]
    for index in range(256):
        n=index<<24
        for _ in range(8):
            n=(((n<<1)^0x04C11DB7) if n & 0x80000000 else n<<1)&0xffffffff
        tab.append(n)
    return tuple(tab)


def ea_crc32(data: bytes) -> int:
    _require(len(data)>=4, 'CRC region too small')
    tab=_crc_table()
    current=(~int.from_bytes(data[:4],'big'))&0xffffffff
    for octet in data[4:]:
        current=((((current<<8)&0xffffffff)|octet)^tab[current>>24])&0xffffffff
    return (~current)&0xffffffff


def _repair_header(buffer: bytearray, order: str, fix_size: bool):
    if fix_size:
        struct.pack_into(order+'I', buffer, 4, len(buffer))
    buffer[-16:]=hashlib.md5(buffer[0x34:-16]).digest()
    for field,start,end in ((0x10,0x1c,0x24),(0x14,0x24,len(buffer)),(0x18,0,0x18)):
        struct.pack_into(order+'I', buffer, field, ea_crc32(buffer[start:end]))


def _check_header(buffer: bytes, order: str, is_pc: bool):
    _require(buffer[:4] == (b'20CM' if is_pc else b'MC02'), 'Incorrect save signature')
    _require(len(buffer)==(PC_BYTES if is_pc else GC_MC02_BYTES), 'Unexpected save size')
    if is_pc:
        _require(struct.unpack_from('<I',buffer,4)[0]==len(buffer),'Incorrect PC size field')
    else:
        _require(struct.unpack_from('>I',buffer,4)[0]==0x12000,'Unsupported GameCube block length')
    _require(hashlib.md5(buffer[0x34:-16]).digest()==buffer[-16:], 'Save MD5 mismatch')
    _require(hashlib.md5(buffer[0x44:0x4034]).digest()==buffer[0x34:0x44], 'Gameplay MD5 mismatch')
    for field,start,end in ((0x10,0x1c,0x24),(0x14,0x24,len(buffer)),(0x18,0,0x18)):
        _require(struct.unpack_from(order+'I',buffer,field)[0]==ea_crc32(buffer[start:end]),f'Save CRC mismatch at 0x{field:X}')


def parse_pc(data: bytes):
    _check_header(data,'<',True)
    _require(data[0x44:0x48]==b'Game', 'Unsupported PC gameplay version')
    _require(int.from_bytes(data[0x48:0x4c],'little')==8,'Unsupported PC gameplay version')
    return data


def _validate_gci_wrapper(data: bytes):
    """Validate the GCI's *outer* file identity and NFSMW media prelude.

    The original v0.2 only checked the embedded MC02, overlooking an invalid
    16-byte wrapper prelude and a directory filename/profile collision.
    """
    _require(data[:6].decode('ascii', errors='replace') in GAMECUBE_REGIONS, 'Unsupported GameCube game ID')
    _require(data[8:13] == b'NFSMW', 'Unsupported GameCube save directory filename')
    _require(int.from_bytes(data[0x38:0x3a], 'big') == 9, 'Unexpected GameCube memory-card block count')
    prelude=data[0x40:0x50]
    total, native_size, native_offset, media_checksum=struct.unpack('>IIII', prelude)
    _require((total,native_size,native_offset) == (0x11531,GC_MC02_BYTES,0x2040),
             'Invalid GameCube media prelude (v0.2 generated files require repair)')
    # NFSMW uses the sum of signed 8-bit bytes across the 0x2040-byte
    # comment+banner/icon region, stored as a 32-bit two's-complement value.
    expected=sum(x if x<128 else x-256 for x in data[0x50:GC_BLOCK_OFFSET]) & 0xffffffff
    _require(media_checksum == expected, 'GameCube media checksum mismatch')
    directory_name=data[8:0x28].split(b'\x00',1)[0]
    _require(directory_name == b'NFSMW'+_name(data[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES]).encode('ascii'),
             'GameCube directory filename does not match internal profile')
    comment_name=data[0x70:0x90].split(b'\x00',1)[0]
    _require(comment_name == directory_name[5:], 'GameCube comment name does not match internal profile')


def parse_gci(data: bytes):
    _require(len(data)==GC_GCI_BYTES,'Expected a 0x12040-byte GameCube .gci file')
    gamecube_game_id(data)
    _require(data[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+4]==b'MC02', 'Cannot find the expected embedded MC02 save')
    native=data[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES]
    _check_header(native,'>',False)
    _require(native[0x44:0x48]==b'emaG','Unsupported GameCube gameplay block')
    _require(int.from_bytes(native[0x48:0x4c],'big')==8,'Unsupported GameCube gameplay version')
    _validate_gci_wrapper(data)
    return native


def _lua_convert(buffer: bytearray, start: int, size: int, to_pc: bool):
    """Convert serialized Lua table tag layout and typed numeric values.

    A valid table alternates key and value entries. For packed string keys,
    evaluate possible null terminators and select the longest valid parse.
    Ambiguous records are rejected rather than guessed.
    """
    stop=start+size
    _require(0<=start<=stop<=len(buffer),'Lua table outside gameplay data')
    def tag(pos):
        b=buffer[pos]
        if to_pc:
            return b>>4, (b>>3)&1, (b>>2)&1, (b>>1)&1, b&1
        return b&15, (b>>4)&1, (b>>5)&1, (b>>6)&1, (b>>7)&1

    @lru_cache(None)
    def options(at, expect_key):
        if at==stop:
            return ((),) if expect_key else ()
        if at>stop:
            return ()
        kind, flag, packed, key, valid=tag(at)
        if not valid:
            return ((),) if expect_key and at==stop-1 and buffer[at]==0 else ()
        if bool(key)!=expect_key or kind not in (1,3,4):
            return ()
        if kind==4:
            ends=[k+1 for k in range(at+1,stop) if buffer[k]==0]
            if not packed: ends=ends[:1]
        else:
            ends=[at+1+(1 if packed else 4) if kind==3 else at+1]
        solutions=[]
        for end in ends:
            for rest in options(end,not expect_key):
                candidate=((at,kind,packed),)+rest
                if solutions and len(candidate)<len(solutions[0]):continue
                if solutions and len(candidate)>len(solutions[0]):solutions.clear()
                if len(solutions)<2:solutions.append(candidate)
        return tuple(solutions)

    parses=options(start,True)
    _require(len(parses)==1,f'Unsupported or ambiguous gameplay Lua table at 0x{start+0x34:X}')
    for pos,kind,packed in parses[0]:
        kind, boolean, packed, key, valid=tag(pos)
        buffer[pos]=(kind|(boolean<<4)|(packed<<5)|(key<<6)|(valid<<7)) if to_pc else ((kind<<4)|(boolean<<3)|(packed<<2)|(key<<1)|valid)
        if kind==3 and not packed:
            _flip(buffer,pos+1,4)


def _convert_gameplay(raw: bytes, to_pc: bool):
    _require(len(raw)==0x4000,'Wrong gameplay size')
    result=bytearray(raw)
    src_order='>' if to_pc else '<'
    _require(result[16:20]==(b'emaG' if to_pc else b'Game'),'Wrong gameplay magic')
    (magic,version,activities,timers,types,milestones,traps,gates,hiding_bits,bin_bytes,sms)=struct.unpack_from(src_order+'11I',result,16)
    _require(version==8 and activities<=256 and timers<=64 and types<=128 and milestones<=256 and traps<=128 and gates<=256 and sms<=256,'Unsupported gameplay counts')
    for off in range(16,60,4):_flip(result,off,4)
    off=0x80
    for _ in range(activities):
        _require(off+16<=len(result),'Truncated persistent activity')
        _,record_size=struct.unpack_from(src_order+'II',result,off)
        _require(record_size>=8 and off+record_size+8<=len(result),'Invalid activity record')
        table_bytes=struct.unpack_from(src_order+'H',result,off+14)[0]
        _require(table_bytes==record_size-8,'Unknown persistent activity layout')
        for delta,width in ((0,4),(4,4),(8,4),(12,2),(14,2)):_flip(result,off+delta,width)
        if table_bytes:_lua_convert(result,off+16,table_bytes,to_pc)
        off+=(record_size+8+15)&~15
    align=lambda n:(n+7)&~7
    for _ in range(timers):
        _flip(result,off,4);_flip(result,off+8,4);off+=32
    off=align(off)
    for _ in range(types):
        for d in (0,4,8,12):_flip(result,off+d,4)
        off+=16
    off=align(off)
    for _ in range(milestones):
        for d,w in ((0,4),(4,4),(10,2),(12,4),(16,4)):_flip(result,off+d,w)
        off+=20
    off=align(off)
    for _ in range(traps):
        for d,w in ((0,2),(2,2),(4,4),(8,4),(12,4),(16,4)):_flip(result,off+d,w)
        off+=20
    off=align(off)
    for _ in range(gates):_flip(result,off,4);off+=4
    off=align(off)
    hiding_bytes=(hiding_bits+7)//8
    _require(hiding_bytes%4==0,'Unexpected hiding spot layout')
    for d in range(0,hiding_bytes,4):_flip(result,off+d,4)
    off=align(off+hiding_bytes)
    _require(bin_bytes>=4 and off+bin_bytes<=len(result),'Unexpected bin stats')
    bin_count=struct.unpack_from(src_order+'I',result,off)[0]
    _require(bin_bytes==4+8*bin_count,'Unexpected bin stats record count')
    _flip(result,off,4)
    for d in range(4,bin_bytes,2):_flip(result,off+d,2)
    off=align(off+bin_bytes)
    for _ in range(sms):_flip(result,off,4);off+=4
    off=align(off)
    _require(off+32<=len(result),'Gameplay footer outside section')
    for d in (8,24):_flip(result,off+d,4)
    result[:16]=hashlib.md5(result[16:]).digest()
    return bytes(result)


def _convert_settings(raw: bytes):
    _require(len(raw)==608,'Unexpected settings length')
    data=bytearray(raw)
    _flip(data,0,2) # adaptive difficulty
    _flip(data,2,4) # career status flags (critical for Continue Career)
    for pos in range(6,606,4):_flip(data,pos+2,2)
    _flip(data,606,2)
    return bytes(data)


def _convert_races(raw: bytes):
    _require(len(raw)==4+300*16,'Unexpected race table size')
    data=bytearray(raw)
    _flip(data,0,4) # number of entries
    for pos in range(4,len(data),16):
        for d,w in ((0,4),(4,4),(8,4),(12,2),(14,2)):_flip(data,pos+d,w)
    return bytes(data)


def _convert_cars(raw: bytes, to_pc: bool):
    _require(len(raw)==119*20,'Unexpected car list size')
    b=bytearray(raw)
    old,new=(0xaa,0xcd) if to_pc else (0xcd,0xaa)
    for pos in range(0,len(b),20):
        for d in (0,4,8,12):_flip(b,pos+d,4)
        if b[pos+18:pos+20]==bytes([old,old]):b[pos+18:pos+20]=bytes([new,new])
    return bytes(b)


def _convert_customizations(raw: bytes, to_pc: bool):
    _require(len(raw)==44*0x198,'Unexpected customization size')
    b=bytearray(raw)
    old,new=(0xaa,0xcd) if to_pc else (0xcd,0xaa)
    for pos in range(0,len(b),0x198):
        for d in range(0,0x116,2):_flip(b,pos+d,2)
        if b[pos+0x116:pos+0x118]==bytes([old,old]):b[pos+0x116:pos+0x118]=bytes([new,new])
        for d in range(0x118,0x194,4):_flip(b,pos+d,4)
        if b[pos+0x195:pos+0x198]==bytes([old])*3:b[pos+0x195:pos+0x198]=bytes([new])*3
    return bytes(b)


def _convert_pursuits(raw: bytes, to_pc: bool):
    _require(len(raw)==25*0x38,'Unexpected pursuit record size')
    b=bytearray(raw)
    old,new=(0xaa,0xcd) if to_pc else (0xcd,0xaa)
    for pos in range(0,len(b),0x38):
        for d in (1,10,11):
            if b[pos+d]==old:b[pos+d]=new
        # Unused pursuits carry 20 extra platform-specific padding bytes.
        if b[pos]==0xff:
            for d in list(range(2,10))+list(range(12,24)):
                if b[pos+d]==old:b[pos+d]=new
        for d in (12,16):_flip(b,pos+d,4)
        for d in range(20,56,2):_flip(b,pos+d,2)
    return bytes(b)


def _convert_history(raw: bytes):
    _require(len(raw)==40,'Unexpected pursuit history size')
    return raw[:4][::-1]+b''.join(raw[k:k+2][::-1] for k in range(4,40,2))

# A source range maps to a target range; all offsets are relative to the
# 20CM / MC02 header, not the .gci file's beginning.
REGIONS=(
    (0x34,0x34,0x4000,'gameplay'),
    (0x4034,0x4034,4,'u32'),
    (0x4038,0x4038,1,'raw'),
    (0x4039,0x4039,4,'u32'),
    (0x403f,0x403f,4,'u32'),  # career started and other status flags
    (0x429d,0x429d,16,'case'),
    (0x42ad,0x42ad,4804,'races'),
    (0x5571,0x5571,456,'raw'),
    (0x5739,0x5739,756,'u32'),
    (0x5a31,0x5a31,36,'raw'),
    (0x6219,0x6255,119*20,'cars'),
    (0x9ccd,0x9d09,44*0x198,'customizations'),
    (0xe2ed,0xe329,25*0x38,'pursuits'),
    (0xe865,0xe8a1,40,'history'),
)


def _transform(raw: bytes, kind: str, to_pc: bool):
    if kind=='raw':return raw
    if kind=='case':return raw[:13]+(b'\xcd'*3 if to_pc else b'\xaa'*3)
    if kind=='u32':return _u32_array(raw)
    if kind=='gameplay':return _convert_gameplay(raw,to_pc)
    if kind=='settings':return _convert_settings(raw)
    if kind=='races':return _convert_races(raw)
    if kind=='cars':return _convert_cars(raw,to_pc)
    if kind=='customizations':return _convert_customizations(raw,to_pc)
    if kind=='pursuits':return _convert_pursuits(raw,to_pc)
    if kind=='history':return _convert_history(raw)
    raise ConversionError('Unknown conversion region')


def _name(data: bytes):
    s=data[0x5a31:0x5a51].split(b'\x00',1)[0]
    _require(s and all(32<=c<127 for c in s),'Unsupported profile name encoding')
    return s.decode('ascii')


def profile_name(data: bytes, source: str):
    return _name(parse_pc(data) if source=='pc' else parse_gci(data))


def _change_cash(native_or_pc: bytearray, cash: int, is_pc: bool):
    _require(0<=cash<=2_000_000_000,'Cash must be between 0 and 2,000,000,000')
    struct.pack_into('<I' if is_pc else '>I',native_or_pc,0x4039,cash)


def _check_car_index(buffer: bytes):
    # Active car must correspond to one of the handles in the car database.
    current=struct.unpack_from('<I',buffer,0x4034)[0]
    if current==0:return
    start=0x5bc5
    handles={struct.unpack_from('<I',buffer,start+i*20)[0] for i in range(200)}
    _require(current in handles,'Current car handle does not exist in the PC car database')


# Built-in assets hold only the platform-specific non-progress fields, with all
# transferable career/garage sections removed. GC high scores are blanked.
# No player names, full user saves, or proprietary banner art are bundled.
@lru_cache(maxsize=3)
def _asset(name: str) -> bytes:
    path = Path(__file__).resolve().parent / 'assets' / name
    try:
        return zlib.decompress(path.read_bytes())
    except (OSError, zlib.error) as exc:
        raise ConversionError(f'Missing or damaged built-in platform data: {name}') from exc


def _built_in_scaffold(platform: str) -> bytes:
    if platform == 'pc':
        raw = _asset('pc_scaffold.z')
        _require(len(raw) == PC_BYTES and raw[:4] == b'20CM',
                 'Invalid bundled PC platform data')
        return raw
    if platform == 'gc':
        raw = _asset('gc_scaffold.z')
        _require(len(raw) == GC_MC02_BYTES and raw[:4] == b'MC02',
                 'Invalid bundled GameCube platform data')
        return raw
    raise ConversionError('Unknown platform')


def _valid_gc_name(name: str) -> str:
    name = name.strip().upper()
    _require(bool(re.fullmatch(r'[A-Z0-9_-]{1,27}',name)),
             'GameCube profile name must be 1-27 ASCII letters, digits, _ or -')
    return name


def _safe_gc_name(pc_name: str) -> str:
    """Default to a *different* internal save ID to avoid overwriting source."""
    return _valid_gc_name(pc_name[:25] + 'GC')


def _rename_native_gc(block: bytearray, name: str):
    """Update serialized profile and career case file, not just .gci basename."""
    encoded = _valid_gc_name(name).encode('ascii')
    block[0x5A31:0x5A55] = encoded.ljust(36,b'\x00')
    # Original case ID follows MW-<number>-<first four chars>XXX, max 12 chars.
    case = block[0x429D:0x42AD].split(b'\x00',1)[0].decode('ascii',errors='ignore')
    match = re.match(r'^(MW-\d+-)',case)
    if match:
        new_case=(match.group(1) + name[:4] + 'XXX')[:12].encode('ascii')
        block[0x429D:0x42AD] = new_case.ljust(13,b'\x00') + b'\xAA'*3


def _fix_gci_prelude(result: bytearray):
    """Rebuild all four 32-bit media fields from the wrapper's actual bytes."""
    checksum=sum(x if x<128 else x-256 for x in result[0x50:GC_BLOCK_OFFSET]) & 0xffffffff
    struct.pack_into('>IIII',result,0x40,0x11531,GC_MC02_BYTES,0x2040,checksum)


def _set_gci_identity(result: bytearray, name: str):
    encoded = _valid_gc_name(name).encode('ascii')
    result[8:0x28] = (b'NFSMW'+encoded).ljust(32,b'\x00')
    result[0x70:0x90] = encoded.ljust(32,b'\x00')
    _fix_gci_prelude(result)


def _wrap_gci(native: bytes, name: str, game_id: str = DEFAULT_GAME_ID) -> bytes:
    """Construct GCI directory entry, valid media prelude, and banner/icon."""
    encoded = _valid_gc_name(name).encode('ascii')
    game_id = _valid_game_id(game_id)
    media = _asset('gc_media.z')
    _require(len(media) == 0x2000, 'Invalid bundled GameCube banner/icon')
    header = bytearray(0x40)
    header[:6] = game_id.encode('ascii')
    header[6] = 0xFF
    header[7] = 2                       # RGB5A3 banner
    header[8:8+5+len(encoded)] = b'NFSMW' + encoded
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    struct.pack_into('>I', header, 0x28, int((now-epoch).total_seconds()))
    struct.pack_into('>I', header, 0x2C, 0x50)
    struct.pack_into('>H', header, 0x30, 0x0002)
    struct.pack_into('>H', header, 0x32, 0x0002)
    header[0x34] = 4
    struct.pack_into('>H', header, 0x36, 0x0049)
    struct.pack_into('>H', header, 0x38, 9)
    struct.pack_into('>H', header, 0x3A, 0xFFFF)
    struct.pack_into('>I', header, 0x3C, 0x10)
    comment = bytearray(0x50)
    comment[0x10:0x10+len(b'NFS Most Wanted')] = b'NFS Most Wanted'
    comment[0x30:0x30+len(encoded)] = encoded
    result = bytearray(bytes(header) + bytes(comment) + media + native)
    _require(len(result) <= GC_GCI_BYTES, 'GCI block allocation exceeded')
    result += bytes(GC_GCI_BYTES - len(result))
    _fix_gci_prelude(result)
    return bytes(result)


def repair_v02_gci(broken_gci: bytes, new_name: str) -> bytes:
    """Repair a v0.2-generated GCI without changing its gameplay/progress."""
    _require(len(broken_gci) == GC_GCI_BYTES and broken_gci[:6] == b'GOWE69',
             'Not a supported USA GOWE GameCube save')
    block = bytearray(broken_gci[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES])
    _check_header(block, '>', False)
    source_name=_name(block)
    target_name=_valid_gc_name(new_name)
    _require(source_name.upper()!=target_name,
             'Choose a different internal name to prevent collision with your original save')
    _rename_native_gc(block,target_name)
    _repair_header(block,'>',False)
    result=bytearray(broken_gci)
    result[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES]=block
    _set_gci_identity(result,target_name)
    parse_gci(bytes(result))
    return bytes(result)


def gc_to_pc(gci: bytes, pc_template: bytes | None = None,
             cash: int | None = None) -> bytes:
    """Convert a structurally compatible GameCube GCI to PC."""
    native = parse_gci(gci)
    pc = bytearray(parse_pc(pc_template) if pc_template is not None
                   else _built_in_scaffold('pc'))
    for pc_at, gc_at, size, kind in REGIONS:
        pc[pc_at:pc_at+size] = _transform(native[gc_at:gc_at+size], kind, True)
    pc[:4] = b'20CM'
    struct.pack_into('<I', pc, 4, PC_BYTES)
    if cash is not None:
        _change_cash(pc, cash, True)
    _repair_header(pc, '<', True)
    parse_pc(bytes(pc))
    return bytes(pc)


def pc_to_gc(pc_save: bytes, gc_template: bytes | None = None,
             cash: int | None = None, *, new_name: str | None = None,
             allow_same_name: bool = False,
             game_id: str = DEFAULT_GAME_ID) -> bytes:
    """Convert PC to GCI. By default use a *different* internal save name.

    Region variants other than GOWE69 remain experimental until in-game tested.
    """
    game_id = _valid_game_id(game_id)
    pc = parse_pc(pc_save)
    source_name = _name(pc)
    name = _valid_gc_name(new_name) if new_name is not None else _safe_gc_name(source_name)
    _require(allow_same_name or name != source_name.upper(),
             'Refusing to create a GameCube save with the same internal name as the source; choose a different profile name')
    if gc_template is not None:
        native = parse_gci(gc_template)
        _require(gamecube_game_id(gc_template) == game_id,
                 'The GameCube template must match the selected destination edition')
        block = bytearray(native)
    else:
        block = bytearray(_built_in_scaffold('gc'))
    for pc_at, gc_at, size, kind in REGIONS:
        block[gc_at:gc_at+size] = _transform(pc[pc_at:pc_at+size], kind, False)
    _rename_native_gc(block,name)
    if cash is not None:
        _change_cash(block, cash, False)
    _repair_header(block, '>', False)
    _check_header(block, '>', False)
    if gc_template is not None:
        out = bytearray(gc_template)
        out[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES] = block
        _set_gci_identity(out,name)
        result = bytes(out)
    else:
        result = _wrap_gci(bytes(block), name, game_id)
    parse_gci(result)
    return result


def gc_to_gc(gci: bytes, target_game_id: str, *,
             new_name: str | None = None, cash: int | None = None) -> bytes:
    """Experimental region conversion: preserve the GC-native gameplay block.

    Rebuild the destination edition's GCI identity and checksum metadata.
    This is not a language translation and cannot prove in-game compatibility
    without a genuine target-region save for comparison.
    """
    source_block = parse_gci(gci)
    source_id = gamecube_game_id(gci)
    target_id = _valid_game_id(target_game_id)
    old_name = _name(source_block)
    name = _valid_gc_name(new_name) if new_name is not None else old_name
    _require(source_id != target_id or name != old_name,
             'Source and target have the same GameCube game ID and profile name. '
             'Choose another destination region or a different profile name.')
    block = bytearray(source_block)
    if name != old_name:
        _rename_native_gc(block, name)
    if cash is not None:
        _change_cash(block, cash, False)
    if name != old_name or cash is not None:
        _repair_header(block, '>', False)
    result = _wrap_gci(bytes(block), name, target_id)
    parse_gci(result)
    # A region-only conversion must leave the native game save byte-identical.
    if name == old_name and cash is None:
        _require(result[GC_BLOCK_OFFSET:GC_BLOCK_OFFSET+GC_MC02_BYTES] == source_block,
                 'Region conversion changed the career payload unexpectedly')
    return result


def describe(data: bytes, platform: str):
    b=parse_pc(data) if platform=='pc' else parse_gci(data)
    order='little' if platform=='pc' else 'big'
    return {
        'name':_name(b),
        'game_id': gamecube_game_id(data) if platform == 'gc' else None,
        'cash':int.from_bytes(b[0x4039:0x403d],order),
        'blacklist':b[0x4038],
        'career_started':bool(int.from_bytes(b[0x403f:0x4043],order)&1),
        'race_entries':int.from_bytes(b[0x42ad:0x42b1],order),
        'gameplay_version':int.from_bytes(b[0x48:0x4c],order),
    }
