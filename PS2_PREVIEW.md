# CrossSave 0.7 preview: PS2 Black Edition

Adds experimental PC/GC -> PS2 .psu and PS2 .psu/raw profile -> PC/GC.
For Vita, import the PS2 .psu through nfsmw-vita 1.3.7 or newer.
Use the top menu: PS2 Black Edition / Vita (preview).

PS2 output requires a valid SLUS-21351 .psu template. It retains the template's
platform settings, stock database and high scores. Transfer scope follows v0.5:
gameplay, money, career status, race records, mapped garage/customizations and
pursuit records. This does not claim transfer of every platform-specific field.
Vita raw profiles and Max Drive .max are not supported by this preview.
Only NTSC-U Black Edition is the intended PS2 target; raw files lack a disc ID,
so their exact edition cannot be established from a checksum alone.

Offline tests pass for the supplied PC, GC and PS2 fixtures, including every
mapped byte except intentional profile/case renaming, checksums, current car
handle, PSU alignment, exact PSU repacking and corrupt-input rejection.
PS2/Vita in-game loading, garage parts and re-saving still require testing.
Do not treat this preview as the final v0.7 release.

Run with Python 3.10+: Start Converter.bat. Or build an EXE with Build Windows EXE.bat.
Public source contains no user saves or PS2 donor data.
