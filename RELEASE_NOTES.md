# NFSMW CrossSave v0.5.0

A standalone Windows GUI for Need for Speed: Most Wanted (2005) save conversion.

## Supported operations

- GameCube (USA) → PC
- PC → GameCube (USA)
- GameCube ↔ GameCube region conversion for GOWE69, GOWP69, GOWD69, GOWF69 and GOWJ13 (other editions await user testing)

## Compatibility

We tested PC ↔ USA GameCube conversions in-game with real career saves. The other listed editions pass offline structure and checksum checks, but await user testing and feedback. Dolphin also lists GOWJ69 (Japan); we have not tested its save format, so it is not currently selectable.

Back up your saves and Dolphin memory card before importing a converted file.

## Using the Windows EXE

Download `NFSMW-CrossSave-v0.5.exe` from the [GitHub Releases page](https://github.com/ChatProductions/NFSMW-CrossSave/releases/latest), run it on Windows, choose a conversion mode, select your save, and click **Convert and verify**. No Python installation is required.

## Building the program

To compile your own EXE, install Python 3.10+ and run `Build Windows EXE.bat`. The repository also contains a GitHub Actions workflow that builds the Windows executable.
