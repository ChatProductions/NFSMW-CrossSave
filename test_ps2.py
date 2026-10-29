"""Run with PC-profile GCI PSU fixtures. User saves are not distributed."""
import sys
from pathlib import Path
import converter_core as c
import ps2_converter as p

def main():
    pc,gc,psu=[Path(x).read_bytes() for x in sys.argv[1:]]
    for label,source in [('PC',pc),('GC',c.gc_to_pc(gc)),('PS2',p.ps2_to_pc(psu))]:
        native=p.pc_to_ps2(source,psu,'CROSS07')
        packed=p.wrap_psu(native,psu)
        assert p.load_ps2(packed)==native
        result=p.ps2_to_pc(packed)
        for a,b,size,kind in c.REGIONS:
            if kind=='case' or a==0x5a31:continue # deliberate profile rename
            assert result[a:a+size]==source[a:a+size],(label,hex(a))
        gc_out=c.pc_to_gc(result,new_name='CROSSGC')
        assert c.describe(gc_out,'gc')['cash']==c.describe(source,'pc')['cash']
        assert c.describe(gc_out,'gc')['blacklist']==c.describe(source,'pc')['blacklist']
        print('PASS',label,'-> PS2 PSU -> PC: every mapped career/garage region preserved; GC output validated')
    for n in [0,1,4,16,24,52,0x4039,len(native)-1]:
        bad=bytearray(native);bad[n]^=1
        try:p.parse_ps2(bytes(bad))
        except c.ConversionError:pass
        else:raise AssertionError(('corruption accepted',n))
    for bad in [psu[:100],psu[:-1],psu+bytes(1)]:
        try:p.unpack_psu(bad)
        except (c.ConversionError,UnicodeError):pass
        else:raise AssertionError('malformed PSU accepted')
    assert p.wrap_psu(p.load_ps2(psu),psu)==psu
    print('PASS supplied PSU repacks byte-identically; damaged profiles and malformed PSU rejected')
if __name__=='__main__':main()
