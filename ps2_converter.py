"""Experimental SLUS-21351 adapter for CrossSave 0.7 preview.
Uses the established v0.5 transferable regions and an explicit PS2 donor.
"""
import hashlib
import re
import struct
import converter_core as c

PS2_BYTES = 62689
PREFIX = 'BASLUS-21351-'

def parse_ps2(data):
    c._require(len(data) == PS2_BYTES and data[:4] == b'20CM', 'Expected a 62,689-byte PS2 profile, not a raw Vita profile.')
    c._require(struct.unpack_from('<I', data, 4)[0] == len(data), 'PS2 size field mismatch')
    c._require(data[0x44:0x48] == b'Game' and struct.unpack_from('<I',data,0x48)[0] == 8, 'Unsupported PS2 gameplay layout')
    c._require(hashlib.md5(data[0x34:-16]).digest() == data[-16:], 'PS2 profile MD5 mismatch')
    c._require(hashlib.md5(data[0x44:0x4034]).digest() == data[0x34:0x44], 'PS2 gameplay MD5 mismatch')
    for field,start,end in ((16,28,36),(20,36,len(data)),(24,0,24)):
        c._require(struct.unpack_from('<I',data,field)[0] == c.ea_crc32(data[start:end]), 'PS2 CRC mismatch')
    c._name(data)
    return data

def unpack_psu(data):
    c._require(len(data) >= 1536, 'Truncated PSU')
    def header(at):
        c._require(at+512 <= len(data), 'Truncated PSU entry')
        h=data[at:at+512]
        name=h[64:96].split(b'\0',1)[0].decode('ascii')
        return h,struct.unpack_from('<I',h,4)[0],name
    root,count,name=header(0)
    c._require(struct.unpack_from('<H',root)[0]&0x20 and name.startswith(PREFIX), 'PSU must be NTSC-U Black Edition SLUS-21351')
    c._require(3 <= count <= 16, 'Unsupported PSU directory count')
    c._require(header(512)[2] == '.' and header(1024)[2] == '..', 'Invalid PSU directory entries')
    entries=[]; at=1536
    for _ in range(count-2):
        h,size,n=header(at)
        c._require(not (struct.unpack_from('<H',h)[0]&0x20), 'Unexpected PSU subdirectory')
        c._require(n not in [x[0] for x in entries] and '/' not in n and '\\' not in n, 'Invalid PSU filename')
        at+=512
        c._require(at+size <= len(data), 'Truncated PSU file')
        entries.append((n,h,data[at:at+size]));at+=(size+1023)//1024*1024
    c._require(at==len(data), 'PSU padding/length mismatch')
    profiles=[x for x in entries if x[0]==name]
    c._require(len(profiles)==1, 'PSU profile missing')
    profile=parse_ps2(profiles[0][2])
    c._require(name==PREFIX+c._name(profile), 'PSU/profile name mismatch')
    return profile,root,data[512:1536],entries

def load_ps2(data):
    if data[:4]==b'20CM': return parse_ps2(data)
    return unpack_psu(data)[0]

def wrap_psu(profile, donor):
    profile=parse_ps2(profile)
    _,root,dots,entries=unpack_psu(donor)
    name=PREFIX+c._name(profile)
    def rename(h,n,size):
        h=bytearray(h);h[64:96]=n.encode('ascii').ljust(32,b'\0');struct.pack_into('<I',h,4,size);return bytes(h)
    out=rename(root,name,len(entries)+2)+dots
    for old,h,b in entries:
        if old.startswith(PREFIX): old=name;b=profile
        out+=rename(h,old,len(b))+b+bytes((-len(b))%1024)
    c._require(unpack_psu(out)[0]==profile, 'PSU verification failed')
    return out

def ps2_to_pc(data):
    source=load_ps2(data);out=bytearray(c._built_in_scaffold('pc'))
    for pc_at,ps2_at,size,kind in c.REGIONS:
        out[pc_at:pc_at+size]=source[ps2_at:ps2_at+size]
    c._repair_header(out,'<',True)
    c.parse_pc(out);c._check_car_index(out)
    return bytes(out)

def pc_to_ps2(data,donor,name):
    source=c.parse_pc(data);out=bytearray(load_ps2(donor))
    c._require(bool(re.fullmatch('[A-Z0-9_-]{1,19}',name)), 'PS2 name must be 1-19 uppercase ASCII letters, digits, _ or -')
    for pc_at,ps2_at,size,kind in c.REGIONS:
        out[ps2_at:ps2_at+size]=source[pc_at:pc_at+size]
    # Keep the donor platform's stable hash, stock cars, video options and high scores.
    out[0x5a31:0x5a55]=name.encode().ljust(36,b'\0')
    case=bytes(out[0x429d:0x42ad]).split(b'\0',1)[0].decode('ascii',errors='ignore')
    match=re.match(r'^(MW-\d+-)',case)
    if match: out[0x429d:0x42ad]=(match.group(1)+name[:4]+'XXX')[:12].encode().ljust(13,b'\0')+b'\xaa'*3
    c._repair_header(out,'<',True)
    parse_ps2(out)
    # A selected car must be in the destination database.
    current=struct.unpack_from('<I',out,0x4034)[0]
    handles={struct.unpack_from('<I',out,0x5c01+i*20)[0] for i in range(200)}
    c._require(current==0 or current in handles, 'Selected car missing in PS2 database')
    return bytes(out)

def convert(data,source,target,donor=None,name='CROSS07'):
    pc=c.parse_pc(data) if source=='PC' else c.gc_to_pc(data) if source=='GC' else ps2_to_pc(data)
    if target=='PC': return bytes(pc)
    if target=='GC': return c.pc_to_gc(pc,new_name=name)
    c._require(donor is not None,'Choose a PS2 Black Edition .psu donor exported by the Vita port or a memory-card tool')
    return wrap_psu(pc_to_ps2(pc,donor,name),donor)
